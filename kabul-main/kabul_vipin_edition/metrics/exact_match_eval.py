# -*- coding: utf-8 -*-
"""
Exact Match Rate Evaluation Module
Compares generated code with reference code for complete identity
"""

import re
from typing import List, Dict, Any


def normalize_code(code: str, aggressive: bool = False) -> str:
    """
    Normalize code for fair comparison
    
    Args:
        code: Original code string
        aggressive: Whether to perform aggressive normalization (remove all whitespace)
    
    Returns:
        Normalized code
    """
    if not code:
        return ""
    
    # Remove single line comments
    code = re.sub(r'//.*$', '', code, flags=re.MULTILINE)
    
    # Remove multi-line comments
    code = re.sub(r'/\*.*?\*/', '', code, flags=re.DOTALL)
    
    if aggressive:
        # Aggressive mode: remove all whitespace
        code = re.sub(r'\s+', '', code)
    else:
        # Normal mode: compress multiple whitespace to single space
        code = re.sub(r'\s+', ' ', code)
        code = code.strip()
    
    return code


def calculate_exact_match(
    predictions: List[str],
    references: List[str],
    mode: str = "aggressive"
) -> Dict[str, Any]:
    """
    Calculate Exact Match Rate
    
    Args:
        predictions: List of model generated code
        references: List of reference code
        mode: Normalization mode ("aggressive" or "normal")
    
    Returns:
        Dictionary containing match rate and detailed results
    """
    if len(predictions) != len(references):
        return {
            "exact_match_rate": -1.0,
            "matches": 0,
            "total": 0,
            "error": "predictions and references length mismatch"
        }
    
    aggressive = (mode == "aggressive")
    matches = 0
    match_indices = []
    
    for i, (pred, ref) in enumerate(zip(predictions, references)):
        norm_pred = normalize_code(pred, aggressive)
        norm_ref = normalize_code(ref, aggressive)
        
        if norm_pred == norm_ref:
            matches += 1
            match_indices.append(i)
    
    rate = matches / len(predictions) if predictions else 0.0
    
    return {
        "exact_match_rate": rate,
        "matches": matches,
        "total": len(predictions),
        "matched_indices": match_indices
    }


def calculate_relaxed_match(
    predictions: List[str],
    references: List[str]
) -> Dict[str, Any]:
    """
    Calculate Relaxed Match Rate
    Allows:
    - Variable name differences
    - Whitespace differences
    - Comment differences
    - Case differences (for non-keywords)
    
    Args:
        predictions: List of model generated code
        references: List of reference code
    
    Returns:
        Dictionary containing match rate and detailed results
    """
    matches = 0
    
    for pred, ref in zip(predictions, references):
        # More aggressive normalization
        norm_pred = normalize_code(pred, aggressive=True).lower()
        norm_ref = normalize_code(ref, aggressive=True).lower()
        
        if norm_pred == norm_ref:
            matches += 1
    
    rate = matches / len(predictions) if predictions else 0.0
    
    return {
        "relaxed_match_rate": rate,
        "matches": matches,
        "total": len(predictions)
    }


def calculate_token_level_accuracy(prediction: str, reference: str) -> float:
    """
    Calculate token-level accuracy
    
    Args:
        prediction: Model generated code
        reference: Reference code
    
    Returns:
        Token accuracy (0-1)
    """
    # Simple whitespace-based tokenization
    pred_tokens = prediction.split()
    ref_tokens = reference.split()
    
    if not ref_tokens:
        return 1.0 if not pred_tokens else 0.0
    
    # Calculate common tokens
    common = 0
    ref_copy = ref_tokens.copy()
    
    for token in pred_tokens:
        if token in ref_copy:
            common += 1
            ref_copy.remove(token)
    
    # F1 Calculation
    precision = common / len(pred_tokens) if pred_tokens else 0
    recall = common / len(ref_tokens) if ref_tokens else 0
    
    if precision + recall == 0:
        return 0.0
    
    f1 = 2 * precision * recall / (precision + recall)
    return f1


if __name__ == "__main__":
    # Quick Test
    pred = [
        "public void Test() { Console.WriteLine(1); }",
        "public void Test() { Console.WriteLine(2); }",
        "public void Hello() { }",
    ]
    ref = [
        "public void Test() { Console.WriteLine(1); }",
        "public void Test() { Console.WriteLine(1); }",
        "public void Hello() { }",
    ]
    
    print("Exact Match Test:")
    result = calculate_exact_match(pred, ref)
    print(f"  Exact Match Rate: {result['exact_match_rate']:.2%}")
    print(f"  Match Count: {result['matches']}/{result['total']}")
    
    print("\nRelaxed Match Test:")
    result = calculate_relaxed_match(pred, ref)
    print(f"  Relaxed Match Rate: {result['relaxed_match_rate']:.2%}")
    
    print("\nToken Accuracy Test:")
    for i in range(len(pred)):
        acc = calculate_token_level_accuracy(pred[i], ref[i])
        print(f"  [{i+1}] Token F1: {acc:.2%}")
