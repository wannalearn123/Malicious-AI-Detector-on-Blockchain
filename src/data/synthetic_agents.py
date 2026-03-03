# src/data/synthetic_agents.py
from datetime import datetime, timedelta
import numpy as np
from typing import List, Dict

class MaliciousAIAgentSimulator:
    """Generate malicious AI agent transactions."""
    
    AGENT_TYPES = {
        'flash_loan': {'complexity': 'high', 'coordination': 'single'},
        'sybil': {'complexity': 'medium', 'coordination': 'multi'},
        'reentrancy': {'complexity': 'high', 'coordination': 'single'},
        'market_manip': {'complexity': 'very_high', 'coordination': 'multi'},
    }
    
    OPCODE_MAP = {
        'CALL': 'f1', 'DELEGATECALL': 'f4', 'SSTORE': '55',
        'FLASHLOAN': 'a9059cbb', 'SWAP': '38ed1739'
    }
    
    def generate_transaction_sequence(self, agent_type: str, n: int = 100) -> List[Dict]:
        """Generate transaction sequence."""
        config = self.AGENT_TYPES[agent_type]
        base_time = datetime.utcnow() - timedelta(hours=24)
        
        return [{
            'timestamp': base_time + timedelta(seconds=i * (1 if config['coordination'] == 'single' else np.random.exponential(300))),
            'gas_used': self._gas_pattern(config['complexity']),
            'value': np.random.exponential(100 if agent_type == 'flash_loan' else 0.1),
            'input_data': '0x' + ''.join(self.OPCODE_MAP.get(k, '00') for k in ['CALL', 'SSTORE']),
            'from_address': self._gen_address(agent_type, i),
            'to_address': '0x' + 'E' * 40,
            'is_malicious': True,
            'block_number': 18000000 + i,
            'nonce': i
        } for i in range(n)]
    
    def _gas_pattern(self, complexity: str) -> int:
        base = {'low': 21000, 'medium': 100000, 'high': 500000, 'very_high': 2000000}
        return int(np.random.normal(base[complexity], base[complexity] * 0.1))
    
    def _gen_address(self, agent_type: str, idx: int) -> str:
        if 'sybil' in agent_type:
            prefix = '0x' + ''.join(f"{np.random.randint(0,16):x}" for _ in range(6))
            return prefix + ''.join(f"{np.random.randint(0,16):x}" for _ in range(34))
        return '0x' + ''.join(f"{np.random.randint(0,16):x}" for _ in range(40))

class BenignAgentSimulator:
    """Generate benign transactions."""
    
    def generate_normal_transactions(self, n: int = 1000) -> List[Dict]:
        base_time = datetime.utcnow() - timedelta(hours=24)
        return [{
            'timestamp': base_time + timedelta(hours=np.random.uniform(0, 24)),
            'gas_used': int(np.random.normal(50000, 10000)),
            'value': np.random.exponential(0.5),
            'input_data': np.random.choice(['0x', '0xa9059cbb']),
            'from_address': '0x' + ''.join(f"{np.random.randint(0,16):x}" for _ in range(40)),
            'to_address': '0x' + ''.join(f"{np.random.randint(0,16):x}" for _ in range(40)),
            'is_malicious': False,
            'block_number': 18000000 + i,
            'nonce': i
        } for i in range(n)]
