import asyncio
import json
import logging
from typing import List, Dict, Optional, AsyncGenerator
from web3 import Web3, AsyncWeb3
from web3.middleware import geth_poa_middleware
from eth_utils import to_checksum_address, keccak
from hexbytes import HexBytes
import aiohttp
from datetime import datetime, timedelta
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EVMDataCollector:
    def __init__(self, rpc_url: str, ws_url: Optional[str] = None, chain: str = "ethereum"):
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        self.async_w3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(rpc_url))
        self.ws_url = ws_url
        self.chain = chain
        
        # Add POA middleware for Polygon/BSC
        if chain in ["polygon", "bsc", "avalanche"]:
            self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)
            self.async_w3.middleware_onion.inject(geth_poa_middleware, layer=0)
            
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
            
    async def get_block_transactions(self, block_number: int) -> List[Dict]:
        """Fetch all transactions from a specific block with traces."""
        try:
            block = await self.async_w3.eth.get_block(block_number, full_transactions=True)
            transactions = []
            
            for tx in block.transactions:
                tx_dict = dict(tx)
                tx_dict['timestamp'] = datetime.fromtimestamp(block.timestamp)
                tx_dict['block_number'] = block_number
                
                # Get transaction receipt for gas used and status
                receipt = await self.async_w3.eth.get_transaction_receipt(tx.hash)
                tx_dict['gas_used'] = receipt.gasUsed
                tx_dict['status'] = receipt.status
                tx_dict['logs'] = [dict(log) for log in receipt.logs]
                
                # Get traces if available (requires debug/trace API)
                try:
                    traces = await self.get_transaction_trace(tx.hash.hex())
                    tx_dict['traces'] = traces
                except Exception as e:
                    logger.warning(f"Could not get traces for {tx.hash.hex()}: {e}")
                    tx_dict['traces'] = []
                    
                transactions.append(tx_dict)
                
            return transactions
            
        except Exception as e:
            logger.error(f"Error fetching block {block_number}: {e}")
            raise
            
    async def get_transaction_trace(self, tx_hash: str) -> List[Dict]:
        """Fetch debug trace for a transaction using debug_traceTransaction."""
        if not self.session:
            raise RuntimeError("Session not initialized. Use async context manager.")
            
        payload = {
            "jsonrpc": "2.0",
            "method": "debug_traceTransaction",
            "params": [tx_hash, {"tracer": "callTracer", "tracerConfig": {"withLog": True}}],
            "id": 1
        }
        
        async with self.session.post(self.w3.provider.endpoint_uri, json=payload) as response:
            result = await response.json()
            if "error" in result:
                # Fallback to standard trace
                return await self._get_standard_trace(tx_hash)
            return [result.get("result", {})]
            
    async def _get_standard_trace(self, tx_hash: str) -> List[Dict]:
        """Fallback to trace_transaction if debug API not available."""
        payload = {
            "jsonrpc": "2.0",
            "method": "trace_transaction",
            "params": [tx_hash],
            "id": 1
        }
        
        async with self.session.post(self.w3.provider.endpoint_uri, json=payload) as response:
            result = await response.json()
            return result.get("result", [])
            
    async def stream_blocks(self, start_block: int, end_block: Optional[int] = None) -> AsyncGenerator[Dict, None]:
        """Stream blocks from start to end (or indefinitely if end is None)."""
        current = start_block
        
        while end_block is None or current <= end_block:
            try:
                block_data = await self.get_block_transactions(current)
                yield {
                    "block_number": current,
                    "transactions": block_data,
                    "timestamp": datetime.utcnow()
                }
                current += 1
                
                # Rate limiting
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Error processing block {current}: {e}")
                await asyncio.sleep(1)
                continue
                
    async def get_contract_bytecode(self, address: str) -> str:
        """Fetch contract bytecode."""
        checksum_addr = to_checksum_address(address)
        code = await self.async_w3.eth.get_code(checksum_addr)
        return code.hex()
        
    async def get_opcode_trace(self, tx_hash: str) -> Dict:
        """Get detailed opcode-level trace."""
        payload = {
            "jsonrpc": "2.0",
            "method": "debug_traceTransaction",
            "params": [tx_hash, {"disableStorage": True, "disableMemory": True, "disableStack": True}],
            "id": 1
        }
        
        async with self.session.post(self.w3.provider.endpoint_uri, json=payload) as response:
            result = await response.json()
            trace = result.get("result", {})
            
            # Parse structLogs to extract opcodes
            opcodes = []
            if "structLogs" in trace:
                for log in trace["structLogs"]:
                    opcodes.append({
                        "pc": log.get("pc"),
                        "op": log.get("op"),
                        "gas": log.get("gas"),
                        "gasCost": log.get("gasCost"),
                        "depth": log.get("depth")
                    })
                    
            return {
                "gas": trace.get("gas"),
                "failed": trace.get("failed"),
                "returnValue": trace.get("returnValue"),
                "opcodes": opcodes,
                "struct_logs_count": len(trace.get("structLogs", []))
            }

class HistoricalDataSync:
    """Sync historical blockchain data to database."""
    
    def __init__(self, collector: EVMDataCollector, db_session, batch_size: int = 100):
        self.collector = collector
        self.db = db_session
        self.batch_size = batch_size
        self.processed_blocks = set()
        
    async def sync_range(self, start_block: int, end_block: int):
        """Sync a range of blocks."""
        tasks = []
        
        async for block_data in self.collector.stream_blocks(start_block, end_block):
            tasks.append(self._process_block(block_data))
            
            if len(tasks) >= self.batch_size:
                await asyncio.gather(*tasks)
                tasks = []
                logger.info(f"Processed up to block {block_data['block_number']}")
                
        if tasks:
            await asyncio.gather(*tasks)
            
    async def _process_block(self, block_data: Dict):
        """Process and store block data."""
        from src.data.models import Transaction, Wallet, TransactionTrace
        
        for tx in block_data["transactions"]:
            # Create or update wallets
            sender = self._get_or_create_wallet(tx["from"])
            receiver = self._get_or_create_wallet(tx.get("to"))
            
            # Create transaction record
            tx_record = Transaction(
                id=tx["hash"].hex() if isinstance(tx["hash"], HexBytes) else tx["hash"],
                block_number=tx["block_number"],
                block_hash=tx["blockHash"].hex() if isinstance(tx.get("blockHash"), HexBytes) else tx.get("blockHash"),
                timestamp=tx["timestamp"],
                from_address=tx["from"],
                to_address=tx.get("to"),
                value=str(tx.get("value", 0)),
                gas=tx.get("gas"),
                gas_price=tx.get("gasPrice"),
                gas_used=tx.get("gas_used"),
                nonce=tx.get("nonce"),
                input_data=tx.get("input", "0x"),
                status=tx.get("status")
            )
            
            self.db.add(tx_record)
            
            # Process traces
            for trace in tx.get("traces", []):
                trace_record = self._parse_trace(tx_record.id, trace)
                self.db.add(trace_record)
                
        self.db.commit()
        
    def _get_or_create_wallet(self, address: str) -> Wallet:
        from src.data.models import Wallet
        
        if not address:
            return None
            
        wallet = self.db.query(Wallet).filter_by(address=address).first()
        if not wallet:
            wallet = Wallet(
                address=address,
                is_contract=self._is_contract(address)
            )
            self.db.add(wallet)
            self.db.flush()
        return wallet
        
    def _is_contract(self, address: str) -> bool:
        """Check if address is a contract."""
        code = self.collector.w3.eth.get_code(to_checksum_address(address))
        return len(code) > 0
        
    def _parse_trace(self, tx_hash: str, trace: Dict) -> TransactionTrace:
        from src.data.models import TransactionTrace
        
        return TransactionTrace(
            tx_hash=tx_hash,
            trace_address=trace.get("traceAddress", []),
            subtraces=trace.get("subtraces"),
            trace_type=trace.get("type"),
            call_type=trace.get("callType"),
            from_address=trace.get("from"),
            to_address=trace.get("to"),
            value=str(trace.get("value", 0)),
            gas=trace.get("gas"),
            gas_used=trace.get("gasUsed"),
            input=trace.get("input"),
            output=trace.get("output"),
            error=trace.get("error")
        )