# -*- coding: utf-8 -*-
"""
DataFlow Match Calculation
Native Tree-sitter implementation with Variable Normalization.
Extracts a sequence of variable usages and normalizes their names to capture logic flow independent of naming.
"""

from .parser_driver import CSharpParser
import tree_sitter

# C# Query to extract variables
ALL_IDS_QUERY = """
(identifier) @id
"""

# C# Keywords and Common Types to Ignore
IGNORED_TOKENS = {
    'abstract', 'as', 'base', 'bool', 'break', 'byte', 'case', 'catch',
    'char', 'checked', 'class', 'const', 'continue', 'decimal', 'default',
    'delegate', 'do', 'double', 'else', 'enum', 'event', 'explicit',
    'extern', 'false', 'finally', 'fixed', 'float', 'for', 'foreach',
    'goto', 'if', 'implicit', 'in', 'int', 'interface', 'internal',
    'is', 'lock', 'long', 'namespace', 'new', 'null', 'object', 'operator',
    'out', 'override', 'params', 'private', 'protected', 'public', 'readonly',
    'ref', 'return', 'sbyte', 'sealed', 'short', 'sizeof', 'stackalloc',
    'static', 'string', 'struct', 'switch', 'this', 'throw', 'true',
    'try', 'typeof', 'uint', 'ulong', 'unchecked', 'unsafe', 'ushort',
    'using', 'virtual', 'void', 'volatile', 'while', 'var', 'async', 'await',
    'get', 'set', 'value', 'dynamic', 'from', 'where', 'select', 'group', 'into',
    'orderby', 'join', 'let', 'on', 'equals', 'by', 'ascending', 'descending',
    # Common Types and System names
    'Console', 'Math', 'List', 'Dictionary', 'HashSet', 'BitConverter', 'Convert',
    'Int32', 'Int64', 'String', 'Boolean', 'Double', 'Object', 'System', 'Exception',
    'WriteLine', 'Write', 'ReadLine', 'ToString', 'Parse', 'TryParse', 
    'Main', 'Program', 'args', 
}

def get_dataflow_sequence(code_bytes, parser):
    """
    Extract and normalize variable sequence
    Example: "int a = 1; int b = a;" -> ["var0", "var1", "var0"]
    """
    try:
        tree = parser.parse(code_bytes)
        root = tree.root_node
        lang = CSharpParser.get_language()
        
        query = lang.query(ALL_IDS_QUERY)
        captures = query.captures(root)
        
        # Sort by appearance in code
        nodes = [node for node, _ in captures]
        nodes.sort(key=lambda n: n.start_byte)
        
        var_map = {}
        next_id = 0
        normalized_sequence = []
        
        for node in nodes:
            token = code_bytes[node.start_byte:node.end_byte].decode('utf-8')
            
            # Filter
            if token in IGNORED_TOKENS or token[0].isupper(): 
                continue
            
            # Normalize
            if token not in var_map:
                var_map[token] = f"var_{next_id}"
                next_id += 1
            
            normalized_sequence.append(var_map[token])
            
        return normalized_sequence
        
    except Exception:
        return []

def calculate_dataflow_match(predictions, references, lang="c_sharp"):
    match_count = 0
    total_count = 0
    
    parser = CSharpParser.get_parser()
    
    for pred, ref in zip(predictions, references):
        try:
            pred_seq = get_dataflow_sequence(pred.encode('utf-8'), parser)
            ref_seq = get_dataflow_sequence(ref.encode('utf-8'), parser)
            
            # Calculate Overlap (Bag-of-Words)
            from collections import Counter
            pred_counter = Counter(pred_seq)
            ref_counter = Counter(ref_seq)
            
            matches = sum((pred_counter & ref_counter).values())
            total = sum(ref_counter.values())
            
            match_count += matches
            total_count += total
            
        except Exception:
            pass
            
    if total_count == 0:
        return 0.0
        
    return match_count / total_count
