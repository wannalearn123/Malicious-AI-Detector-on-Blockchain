# src/data/synthetic_agents.py
from datetime import datetime, timedelta
import numpy as np
from typing import List, Dict

class MaliciousAIAgentSimulator:
    """Generate malicious AI agent transactions."""
    
    AGENT_TYPES = {
        'flash_loan_attacker': {'behavior': 'atomic_arbitrage', 'complexity': 'high', 'coordination': 'single', 'signature': ['FLASHLOAN', 'SWAP', 'FLASHLOAN']},
        'sybil_coordinator': {'behavior': 'multi_account_coordination', 'complexity': 'medium', 'coordination': 'multi', 'signature': ['CALL', 'SSTORE', 'CALL']},
        'reentrancy_bot': {'behavior': 'recursive_call_exploit', 'complexity': 'high', 'coordination': 'single', 'signature': ['CALL', 'SSTORE', 'CALL']},
        'market_manipulator': {'behavior': 'price_manipulation', 'complexity': 'very_high', 'coordination': 'multi', 'signature': ['SWAP', 'SWAP', 'SWAP']},
        'context_manipulator': {'behavior': 'fake_memory_injection', 'complexity': 'high', 'coordination': 'single', 'signature': ['DELEGATECALL', 'SSTORE', 'LOG1']}
    }
    
    OPCODE_HEX = {
        'CALL': 'f1', 'DELEGATECALL': 'f4', 'STATICCALL': 'fa', 'SSTORE': '55', 'SLOAD': '54',
        'FLASHLOAN': 'a9059cbb', 'SWAP': '38ed1739', 'LOG1': 'a1', 'MSTORE': '52', 'RETURN': 'f3'
    }
    
    def generate_transaction_sequence(self, agent_type: str, num_transactions: int = 100, time_window_hours: int = 24) -> List[Dict]:
        config = self.AGENT_TYPES[agent_type]
        base_time = datetime.utcnow() - timedelta(hours=time_window_hours)
        transactions = []
        
        for i in range(num_transactions):
            if config['coordination'] == 'multi':
                tx_time = base_time + timedelta(hours=np.random.exponential(time_window_hours/10), seconds=np.random.randint(0, 60))
            else:
                interval = 1 if config['behavior'] == 'atomic_arbitrage' else np.random.normal(300, 30)
                tx_time = base_time + timedelta(seconds=i * interval)
            
            transactions.append({
                'timestamp': tx_time,
                'gas_used': self._generate_gas_pattern(config['complexity']),
                'value': self._generate_value_pattern(config['behavior']),
                'input_data': self._generate_input_pattern(config['signature']),
                'from_address': self._generate_address(agent_type, i),
                'to_address': self._generate_target_address(config['behavior']),
                'agent_type': agent_type,
                'is_malicious': True,
                'block_number': 18000000 + i,
                'gas': int(self._generate_gas_pattern(config['complexity']) * 1.2),
                'nonce': i
            })
        
        return transactions
    
    def _generate_gas_pattern(self, complexity: str) -> int:
        base = {'low': 21000, 'medium': 100000, 'high': 500000, 'very_high': 2000000}
        return int(np.random.normal(base[complexity], base[complexity] * 0.1))
    
    def _generate_value_pattern(self, behavior: str) -> float:
        patterns = {'atomic_arbitrage': np.random.exponential(100), 'multi_account_coordination': np.random.uniform(0.01, 0.1), 
                   'recursive_call_exploit': np.random.exponential(50), 'price_manipulation': np.random.exponential(500), 
                   'fake_memory_injection': np.random.uniform(0.001, 0.01)}
        return patterns.get(behavior, 0.1)
    
    def _generate_input_pattern(self, signature: List[str]) -> str:
        bytecode = "0x"
        for op in signature:
            bytecode += self.OPCODE_HEX.get(op, '00')
        return bytecode + '00' * max(0, 10 - len(bytecode))
    
    def _generate_address(self, agent_type: str, index: int) -> str:
        if 'sybil' in agent_type:
            prefix = "0x" + "".join([f"{np.random.randint(0,16):x}" for _ in range(6)])
            return prefix + "".join([f"{np.random.randint(0,16):x}" for _ in range(34)])
        return "0x" + "".join([f"{np.random.randint(0,16):x}" for _ in range(40)])
    
    def _generate_target_address(self, behavior: str) -> str:
        targets = {'atomic_arbitrage': ['0xE592427A0AEce92De3Edee1F18E0157C05861564'], 
                  'recursive_call_exploit': ['0x' + "a"*40], 'price_manipulation': ['0xdAC17F958D2ee523a2206206994597C13D831ec7']}
        return np.random.choice(targets.get(behavior, ['0x' + "0"*40]))

class BenignAgentSimulator:
    """Generate normal/benign transactions."""
    
    def generate_normal_transactions(self, num_transactions: int = 1000) -> List[Dict]:
        base_time = datetime.utcnow() - timedelta(hours=24)
        transactions = []
        
        for i in range(num_transactions):
            tx_time = base_time + timedelta(hours=np.random.uniform(0, 24), minutes=np.random.uniform(0, 60))
            transactions.append({
                'timestamp': tx_time,
                'gas_used': int(np.random.normal(50000, 10000)),
                'value': np.random.exponential(0.5),
                'input_data': np.random.choice(['0x', '0xa9059cbb', '0x095ea7b3']),
                'from_address': "0x" + "".join([f"{np.random.randint(0,16):x}" for _ in range(40)]),
                'to_address': "0x" + "".join([f"{np.random.randint(0,16):x}" for _ in range(40)]),
                'agent_type': 'normal_user',
                'is_malicious': False,
                'block_number': 18000000 + i,
                'gas': int(np.random.normal(60000, 12000)),
                'nonce': np.random.randint(0, 100)
            })
        return transactions
