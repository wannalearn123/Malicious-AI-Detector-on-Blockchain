import re
import math
from collections import Counter, defaultdict
from typing import List, Dict, Tuple, Set
import numpy as np

# Complete EVM Opcode Set with gas costs and categories
OPCODE_MAP = {
    # Stop and Arithmetic
    0x00: ("STOP", 0, "halt"),
    0x01: ("ADD", 3, "arithmetic"),
    0x02: ("MUL", 5, "arithmetic"),
    0x03: ("SUB", 3, "arithmetic"),
    0x04: ("DIV", 5, "arithmetic"),
    0x05: ("SDIV", 5, "arithmetic"),
    0x06: ("MOD", 5, "arithmetic"),
    0x07: ("SMOD", 5, "arithmetic"),
    0x08: ("ADDMOD", 8, "arithmetic"),
    0x09: ("MULMOD", 8, "arithmetic"),
    0x0A: ("EXP", 10, "arithmetic"),
    0x0B: ("SIGNEXTEND", 5, "arithmetic"),
    
    # Comparison & Bitwise Logic
    0x10: ("LT", 3, "comparison"),
    0x11: ("GT", 3, "comparison"),
    0x12: ("SLT", 3, "comparison"),
    0x13: ("SGT", 3, "comparison"),
    0x14: ("EQ", 3, "comparison"),
    0x15: ("ISZERO", 3, "comparison"),
    0x16: ("AND", 3, "bitwise"),
    0x17: ("OR", 3, "bitwise"),
    0x18: ("XOR", 3, "bitwise"),
    0x19: ("NOT", 3, "bitwise"),
    0x1A: ("BYTE", 3, "bitwise"),
    0x1B: ("SHL", 3, "bitwise"),
    0x1C: ("SHR", 3, "bitwise"),
    0x1D: ("SAR", 3, "bitwise"),
    
    # SHA3
    0x20: ("SHA3", 30, "crypto"),
    
    # Environmental Information
    0x30: ("ADDRESS", 2, "env"),
    0x31: ("BALANCE", 400, "env"),  # Changed to warm/cold in Berlin
    0x32: ("ORIGIN", 2, "env"),
    0x33: ("CALLER", 2, "env"),
    0x34: ("CALLVALUE", 2, "env"),
    0x35: ("CALLDATALOAD", 3, "env"),
    0x36: ("CALLDATASIZE", 2, "env"),
    0x37: ("CALLDATACOPY", 3, "env"),
    0x38: ("CODESIZE", 2, "env"),
    0x39: ("CODECOPY", 3, "env"),
    0x3A: ("GASPRICE", 2, "env"),
    0x3B: ("EXTCODESIZE", 700, "env"),
    0x3C: ("EXTCODECOPY", 700, "env"),
    0x3D: ("RETURNDATASIZE", 2, "env"),
    0x3E: ("RETURNDATACOPY", 3, "env"),
    0x3F: ("EXTCODEHASH", 700, "env"),
    
    # Block Information
    0x40: ("BLOCKHASH", 20, "block"),
    0x41: ("COINBASE", 2, "block"),
    0x42: ("TIMESTAMP", 2, "block"),
    0x43: ("NUMBER", 2, "block"),
    0x44: ("DIFFICULTY", 2, "block"),
    0x45: ("GASLIMIT", 2, "block"),
    0x46: ("CHAINID", 2, "block"),
    0x47: ("SELFBALANCE", 5, "block"),
    0x48: ("BASEFEE", 2, "block"),
    
    # Stack, Memory, Storage and Flow Operations
    0x50: ("POP", 2, "stack"),
    0x51: ("MLOAD", 3, "memory"),
    0x52: ("MSTORE", 3, "memory"),
    0x53: ("MSTORE8", 3, "memory"),
    0x54: ("SLOAD", 200, "storage"),  # Warm: 100, Cold: 2100 (Berlin)
    0x55: ("SSTORE", 20000, "storage"),  # Complex gas logic
    0x56: ("JUMP", 8, "flow"),
    0x57: ("JUMPI", 10, "flow"),
    0x58: ("PC", 2, "flow"),
    0x59: ("MSIZE", 2, "memory"),
    0x5A: ("GAS", 2, "flow"),
    0x5B: ("JUMPDEST", 1, "flow"),
    
    # Push Operations
    0x60: ("PUSH1", 3, "push"),
    0x61: ("PUSH2", 3, "push"),
    0x62: ("PUSH3", 3, "push"),
    0x63: ("PUSH4", 3, "push"),
    0x64: ("PUSH5", 3, "push"),
    0x65: ("PUSH6", 3, "push"),
    0x66: ("PUSH7", 3, "push"),
    0x67: ("PUSH8", 3, "push"),
    0x68: ("PUSH9", 3, "push"),
    0x69: ("PUSH10", 3, "push"),
    0x6A: ("PUSH11", 3, "push"),
    0x6B: ("PUSH12", 3, "push"),
    0x6C: ("PUSH13", 3, "push"),
    0x6D: ("PUSH14", 3, "push"),
    0x6E: ("PUSH15", 3, "push"),
    0x6F: ("PUSH16", 3, "push"),
    0x70: ("PUSH17", 3, "push"),
    0x71: ("PUSH18", 3, "push"),
    0x72: ("PUSH19", 3, "push"),
    0x73: ("PUSH20", 3, "push"),
    0x74: ("PUSH21", 3, "push"),
    0x75: ("PUSH22", 3, "push"),
    0x76: ("PUSH23", 3, "push"),
    0x77: ("PUSH24", 3, "push"),
    0x78: ("PUSH25", 3, "push"),
    0x79: ("PUSH26", 3, "push"),
    0x7A: ("PUSH27", 3, "push"),
    0x7B: ("PUSH28", 3, "push"),
    0x7C: ("PUSH29", 3, "push"),
    0x7D: ("PUSH30", 3, "push"),
    0x7E: ("PUSH31", 3, "push"),
    0x7F: ("PUSH32", 3, "push"),
    
    # Duplication Operations
    0x80: ("DUP1", 3, "dup"),
    0x81: ("DUP2", 3, "dup"),
    0x82: ("DUP3", 3, "dup"),
    0x83: ("DUP4", 3, "dup"),
    0x84: ("DUP5", 3, "dup"),
    0x85: ("DUP6", 3, "dup"),
    0x86: ("DUP7", 3, "dup"),
    0x87: ("DUP8", 3, "dup"),
    0x88: ("DUP9", 3, "dup"),
    0x89: ("DUP10", 3, "dup"),
    0x8A: ("DUP11", 3, "dup"),
    0x8B: ("DUP12", 3, "dup"),
    0x8C: ("DUP13", 3, "dup"),
    0x8D: ("DUP14", 3, "dup"),
    0x8E: ("DUP15", 3, "dup"),
    0x8F: ("DUP16", 3, "dup"),
    
    # Exchange Operations
    0x90: ("SWAP1", 3, "swap"),
    0x91: ("SWAP2", 3, "swap"),
    0x92: ("SWAP3", 3, "swap"),
    0x93: ("SWAP4", 3, "swap"),
    0x94: ("SWAP5", 3, "swap"),
    0x95: ("SWAP6", 3, "swap"),
    0x96: ("SWAP7", 3, "swap"),
    0x97: ("SWAP8", 3, "swap"),
    0x98: ("SWAP9", 3, "swap"),
    0x99: ("SWAP10", 3, "swap"),
    0x9A: ("SWAP11", 3, "swap"),
    0x9B: ("SWAP12", 3, "swap"),
    0x9C: ("SWAP13", 3, "swap"),
    0x9D: ("SWAP14", 3, "swap"),
    0x9E: ("SWAP15", 3, "swap"),
    0x9F: ("SWAP16", 3, "swap"),
    
    # Logging Operations
    0xA0: ("LOG0", 375, "log"),
    0xA1: ("LOG1", 750, "log"),
    0xA2: ("LOG2", 1125, "log"),
    0xA3: ("LOG3", 1500, "log"),
    0xA4: ("LOG4", 1875, "log"),
    
    # System operations
    0xF0: ("CREATE", 32000, "system"),
    0xF1: ("CALL", 700, "system"),  # Complex gas
    0xF2: ("CALLCODE", 700, "system"),
    0xF3: ("RETURN", 0, "system"),
    0xF4: ("DELEGATECALL", 700, "system"),
    0xF5: ("CREATE2", 32000, "system"),
    0xFA: ("STATICCALL", 700, "system"),
    0xFD: ("REVERT", 0, "system"),
    0xFE: ("INVALID", 0, "system"),
    0xFF: ("SELFDESTRUCT", 5000, "system"),  # Changed to 5000 (EIP-150)
}

class OpcodeAnalyzer:
    """Analyze EVM opcode sequences for malicious patterns."""
    
    # Known malicious patterns
    REENTRANCY_SIGNATURES = [
        ["CALL", "SLOAD"],
        ["CALL", "SSTORE"],
        ["DELEGATECALL", "SSTORE"],
        ["STATICCALL", "SSTORE"]
    ]
    
    FLASH_LOAN_SIGNATURES = [
        ["FLASHLOAN", "SWAP", "FLASHLOAN"],
        ["BALANCE", "CALL", "BALANCE"]
    ]
    
    def __init__(self):
        self.opcode_list = [info[0] for info in OPCODE_MAP.values()]
        self.category_map = defaultdict(list)
        
        for opcode, (name, gas, category) in OPCODE_MAP.items():
            self.category_map[category].append(name)
            
    def parse_bytecode(self, bytecode: str) -> List[str]:
        """Parse raw bytecode into opcode sequence."""
        if bytecode.startswith('0x'):
            bytecode = bytecode[2:]
            
        opcodes = []
        i = 0
        while i < len(bytecode):
            if i + 2 > len(bytecode):
                break
                
            byte = int(bytecode[i:i+2], 16)
            
            if byte in OPCODE_MAP:
                name, _, _ = OPCODE_MAP[byte]
                opcodes.append(name)
                
                # Handle PUSH operations with immediate data
                if 0x60 <= byte <= 0x7F:
                    push_size = byte - 0x60 + 1
                    i += 2 + (push_size * 2)
                else:
                    i += 2
            else:
                # Invalid opcode
                opcodes.append(f"INVALID_{byte:02X}")
                i += 2
                
        return opcodes
        
    def extract_features(self, opcode_sequence: List[str]) -> Dict:
        """Extract comprehensive features from opcode sequence."""
        if not opcode_sequence:
            return self._empty_features()
            
        features = {}
        counter = Counter(opcode_sequence)
        total = len(opcode_sequence)
        
        # 1. Basic statistics
        features['total_opcodes'] = total
        features['unique_opcodes'] = len(counter)
        features['opcode_diversity'] = len(counter) / total if total > 0 else 0
        
        # 2. Category frequencies
        category_counts = defaultdict(int)
        for op, count in counter.items():
            cat = self._get_category(op)
            category_counts[cat] += count
            
        for cat in self.category_map.keys():
            features[f'cat_{cat}_ratio'] = category_counts[cat] / total if total > 0 else 0
            
        # 3. Opcode frequency vector (normalized)
        for opcode in self.opcode_list:
            features[f'op_{opcode}'] = counter.get(opcode, 0) / total if total > 0 else 0
            
        # 4. Entropy-based features (complexity)
        features['entropy'] = self._calculate_entropy(counter, total)
        
        # 5. Control flow complexity
        features['jump_count'] = counter.get('JUMP', 0) + counter.get('JUMPI', 0)
        features['jumpdest_count'] = counter.get('JUMPDEST', 0)
        features['jump_ratio'] = features['jump_count'] / total if total > 0 else 0
        
        # 6. Memory and storage operations
        features['sload_count'] = counter.get('SLOAD', 0)
        features['sstore_count'] = counter.get('SSTORE', 0)
        features['memory_ops'] = sum(counter.get(op, 0) for op in ['MLOAD', 'MSTORE', 'MSTORE8'])
        
        # 7. External call patterns
        features['call_count'] = counter.get('CALL', 0)
        features['delegatecall_count'] = counter.get('DELEGATECALL', 0)
        features['staticcall_count'] = counter.get('STATICCALL', 0)
        features['external_call_ratio'] = (
            (features['call_count'] + features['delegatecall_count'] + features['staticcall_count']) / total 
            if total > 0 else 0
        )
        
        # 8. Arithmetic complexity
        arithmetic_ops = ['ADD', 'MUL', 'SUB', 'DIV', 'SDIV', 'SMOD', 'EXP']
        features['arithmetic_intensity'] = sum(counter.get(op, 0) for op in arithmetic_ops) / total if total > 0 else 0
        
        # 9. N-gram patterns (2-gram and 3-gram)
        bigrams = self._extract_ngrams(opcode_sequence, 2)
        trigrams = self._extract_ngrams(opcode_sequence, 3)
        
        features['unique_bigrams'] = len(set(bigrams))
        features['unique_trigrams'] = len(set(trigrams))
        
        # 10. Specific vulnerability indicators
        features['reentrancy_risk'] = self._detect_reentrancy_pattern(opcode_sequence)
        features['timestamp_dependency'] = 1 if 'TIMESTAMP' in counter and 'SSTORE' in counter else 0
        features['tx_origin_usage'] = counter.get('ORIGIN', 0)
        
        return features
        
    def _empty_features(self) -> Dict:
        """Return feature dict with zeros."""
        features = {
            'total_opcodes': 0,
            'unique_opcodes': 0,
            'opcode_diversity': 0,
            'entropy': 0,
            'jump_count': 0,
            'jumpdest_count': 0,
            'jump_ratio': 0,
            'sload_count': 0,
            'sstore_count': 0,
            'memory_ops': 0,
            'call_count': 0,
            'delegatecall_count': 0,
            'staticcall_count': 0,
            'external_call_ratio': 0,
            'arithmetic_intensity': 0,
            'unique_bigrams': 0,
            'unique_trigrams': 0,
            'reentrancy_risk': 0,
            'timestamp_dependency': 0,
            'tx_origin_usage': 0,
            'reentrancy_risk_score': 0.0
        }
        
        # Add category ratios
        for cat in self.category_map.keys():
            features[f'cat_{cat}_ratio'] = 0
            
        # Add individual opcode frequencies
        for opcode in self.opcode_list:
            features[f'op_{opcode}'] = 0
            
        return features
        
    def _get_category(self, opcode: str) -> str:
        """Get category for an opcode."""
        for code, (name, _, cat) in OPCODE_MAP.items():
            if name == opcode:
                return cat
        return "unknown"
        
    def _calculate_entropy(self, counter: Counter, total: int) -> float:
        """Calculate Shannon entropy of opcode distribution."""
        if total == 0:
            return 0.0
            
        entropy = 0.0
        for count in counter.values():
            if count > 0:
                p = count / total
                entropy -= p * math.log2(p)
        return entropy
        
    def _extract_ngrams(self, sequence: List[str], n: int) -> List[Tuple]:
        """Extract n-grams from sequence."""
        return [tuple(sequence[i:i+n]) for i in range(len(sequence)-n+1)]
        
    def _detect_reentrancy_pattern(self, sequence: List[str]) -> int:
        """Detect potential reentrancy vulnerability patterns."""
        score = 0
        
        # Look for CALL followed by SSTORE without checks
        for i in range(len(sequence) - 1):
            if sequence[i] in ['CALL', 'DELEGATECALL', 'STATICCALL']:
                # Check if SSTORE appears after without SLOAD in between (checks-effects-interactions violation)
                subsequent = sequence[i+1:min(i+10, len(sequence))]
                if 'SSTORE' in subsequent:
                    sstore_idx = subsequent.index('SSTORE')
                    if 'SLOAD' not in subsequent[:sstore_idx]:
                        score += 1
                        
        return min(score, 5)  # Cap at 5
        
    def analyze_execution_trace(self, struct_logs: List[Dict]) -> Dict:
        """Analyze runtime execution trace from debug_traceTransaction."""
        opcodes = [log.get('op') for log in struct_logs if log.get('op')]
        features = self.extract_features(opcodes)
        
        # Add runtime-specific features
        features['execution_depth'] = max((log.get('depth', 0) for log in struct_logs), default=0)
        features['total_gas_used'] = sum(log.get('gasCost', 0) for log in struct_logs)
        features['memory_expansion_events'] = sum(1 for log in struct_logs if log.get('op') in ['MSTORE', 'MSTORE8', 'MLOAD'])
        
        # Gas efficiency metrics
        if features['total_opcodes'] > 0:
            features['avg_gas_per_op'] = features['total_gas_used'] / features['total_opcodes']
        else:
            features['avg_gas_per_op'] = 0
            
        return features
        
    def get_feature_vector(self, features: Dict) -> np.ndarray:
        """Convert feature dict to numpy array for ML models."""
        # Ensure consistent ordering
        keys = sorted(features.keys())
        return np.array([features[k] for k in keys])