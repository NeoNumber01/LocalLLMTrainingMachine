# -*- coding: utf-8 -*-
"""
Syntax Match (AST) Calculation
Based on CodeBLEU implementation but using native tree-sitter API.
"""

from .parser_driver import CSharpParser

def get_all_subtrees(root_node):
    node_stack = []
    subtrees = []
    
    # Depth-First Traversal
    # Official CodeBLEU: Extract all subtrees (AST structure)
    # We collect the "type" sequence of each node as the signature of that subtree
    
    def visit(node):
        # Collect type of current node and its direct children as signature
        # Like: (binary_expression (identifier) (number))
        signature = [node.type]
        for child in node.children:
            signature.append(child.type)
            visit(child)
        
        # Keep only non-leaf nodes or specific nodes
        if len(node.children) > 0:
            subtrees.append(tuple(signature))
            
    visit(root_node)
    return subtrees

def calculate_syntax_match(predictions, references, lang="c_sharp"):
    match_count = 0
    total_count = 0
    
    for pred, ref in zip(predictions, references):
        try:
            # Parse Prediction
            pred_tree = CSharpParser.parse(pred.encode('utf-8'))
            pred_subtrees = get_all_subtrees(pred_tree.root_node)
            
            # Parse Reference
            ref_tree = CSharpParser.parse(ref.encode('utf-8'))
            ref_subtrees = get_all_subtrees(ref_tree.root_node)
            
            # Count Matches
            from collections import Counter
            pred_counter = Counter(pred_subtrees)
            ref_counter = Counter(ref_subtrees)
            
            matches = sum((pred_counter & ref_counter).values())
            total = sum(ref_counter.values())
            
            match_count += matches
            total_count += total
            
        except Exception as e:
            print(f"Syntax match error: {e}")
            
    if total_count == 0:
        return 0.0
        
    return match_count / total_count
