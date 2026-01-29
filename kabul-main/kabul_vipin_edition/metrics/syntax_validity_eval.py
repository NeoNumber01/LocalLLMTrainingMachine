# -*- coding: utf-8 -*-
"""
Syntax Validity Evaluation Module (Syntax Validity / AST Parse Rate)
Uses Tree-sitter to check if generated C# code can be successfully parsed into an AST

This is a looser, faster syntax check than compilation:
- Compilation: Requires .NET SDK, checks full semantic correctness
- Syntax Validity: Only checks if it can be parsed into a valid AST
"""

from typing import List, Tuple, Dict, Any, Optional
import sys
import os

# Add native_codebleu path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from .native_codebleu.parser_driver import CSharpParser


def check_syntax_validity(code: str) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """
    Check if a single C# code snippet can be successfully parsed by Tree-sitter
    
    Args:
        code: C# code string
    
    Returns:
        Tuple[bool, Optional[str], Dict]:
            - is_valid: Whether syntax is valid
            - error_type: Error type (if any)
            - details: Detailed info dictionary (including AST node count, error positions, etc.)
    """
    if not code or not code.strip():
        return False, "empty_code", {"error": "Empty or whitespace-only code"}
    
    try:
        # Parse using Tree-sitter
        tree = CSharpParser.parse(code.encode('utf-8'))
        root = tree.root_node
        
        # Collect statistics
        details = {
            "total_nodes": 0,
            "error_nodes": 0,
            "missing_nodes": 0,
            "error_positions": [],
        }
        
        # Traverse AST to find ERROR nodes
        def count_errors(node, depth=0):
            details["total_nodes"] += 1
            
            # Check ERROR node (syntax error)
            if node.type == "ERROR":
                details["error_nodes"] += 1
                details["error_positions"].append({
                    "line": node.start_point[0] + 1,
                    "column": node.start_point[1],
                    "text": code[node.start_byte:node.end_byte][:50]
                })
            
            # Check MISSING node (missing syntax element)
            if node.is_missing:
                details["missing_nodes"] += 1
            
            # Recursively check children
            for child in node.children:
                count_errors(child, depth + 1)
        
        count_errors(root)
        
        # Determine validity
        # Strategy: If ERROR nodes exceed 10% of total nodes or there are more than 3 errors, consider invalid
        total = details["total_nodes"]
        errors = details["error_nodes"] + details["missing_nodes"]
        
        if total == 0:
            return False, "empty_ast", details
        
        error_ratio = errors / total
        is_valid = (errors == 0) or (error_ratio < 0.1 and errors <= 3)
        
        if is_valid:
            return True, None, details
        else:
            error_type = "syntax_error" if details["error_nodes"] > 0 else "missing_tokens"
            return False, error_type, details
            
    except Exception as e:
        return False, "parse_exception", {"error": str(e)}


def calculate_syntax_validity_rate(
    predictions: List[str],
    verbose: bool = False
) -> Dict[str, Any]:
    """
    Calculate syntax validity rate for a batch of code
    
    Args:
        predictions: List of model generated code
        verbose: Whether to print detailed info
    
    Returns:
        Dictionary containing syntax validity rate and detailed results
    """
    if not predictions:
        return {
            "syntax_validity_rate": 0.0,
            "valid_count": 0,
            "total": 0,
            "error_breakdown": {},
        }
    
    valid_count = 0
    error_breakdown = {}
    failed_samples = []
    
    for i, code in enumerate(predictions):
        is_valid, error_type, details = check_syntax_validity(code)
        
        if is_valid:
            valid_count += 1
            if verbose:
                print(f"  [{i+1}/{len(predictions)}] ✓ Syntax Valid (Nodes: {details.get('total_nodes', 0)})")
        else:
            # Count error types
            error_breakdown[error_type] = error_breakdown.get(error_type, 0) + 1
            
            if verbose:
                print(f"  [{i+1}/{len(predictions)}] ✗ Syntax Invalid: {error_type}")
                if details.get("error_positions"):
                    for pos in details["error_positions"][:2]:
                        print(f"      Line {pos['line']}: {pos['text'][:30]}...")
            
            # Keep top 10 failed samples details
            if len(failed_samples) < 10:
                failed_samples.append({
                    "index": i,
                    "error_type": error_type,
                    "details": details
                })
    
    rate = valid_count / len(predictions)
    
    return {
        "syntax_validity_rate": rate,
        "valid_count": valid_count,
        "total": len(predictions),
        "error_breakdown": error_breakdown,
        "failed_samples": failed_samples,
    }


def get_ast_summary(code: str) -> Dict[str, Any]:
    """
    Get AST structure summary of code
    
    Args:
        code: C# code string
    
    Returns:
        AST structure summary dictionary
    """
    is_valid, error_type, details = check_syntax_validity(code)
    
    summary = {
        "is_valid": is_valid,
        "error_type": error_type,
        **details
    }
    
    if is_valid:
        try:
            tree = CSharpParser.parse(code.encode('utf-8'))
            root = tree.root_node
            
            # Collect top-level node types
            top_level_nodes = []
            for child in root.children:
                if child.type != "comment":
                    top_level_nodes.append(child.type)
            
            summary["top_level_nodes"] = top_level_nodes
            
        except Exception:
            pass
    
    return summary


if __name__ == "__main__":
    # Quick Test
    print("=" * 50)
    print("Syntax Validity Evaluation Module Test")
    print("=" * 50)
    
    test_codes = [
        # Correct code
        "public class Test { public void Hello() { Console.WriteLine(\"Hi\"); } }",
        # Code with syntax error (missing bracket)
        "public class Test { public void Hello( { Console.WriteLine(\"Hi\"); } }",
        # Correct code using LINQ
        "public class Test { public int[] GetEven(int[] arr) { return arr.Where(x => x % 2 == 0).ToArray(); } }",
        # Incomplete code
        "public class Test {",
        # Empty code
        "",
        # Code snippet with only method
        "public int Add(int a, int b) { return a + b; }",
    ]
    
    print("\nSingle Code Check:")
    for i, code in enumerate(test_codes):
        is_valid, error_type, details = check_syntax_validity(code)
        status = "✓" if is_valid else "✗"
        code_preview = code[:40] + "..." if len(code) > 40 else code
        print(f"  [{i+1}] {status} {code_preview}")
        if error_type:
            print(f"      Error Type: {error_type}")
    
    print("\nBatch Syntax Validity Rate:")
    result = calculate_syntax_validity_rate(test_codes, verbose=True)
    print(f"\n  Syntax Validity Rate: {result['syntax_validity_rate']:.2%} ({result['valid_count']}/{result['total']})")
    print(f"  Error Distribution: {result['error_breakdown']}")
