#!/usr/bin/env python3
"""
Test Script: Verify dual-style code support
Test whether function-style code can execute correctly in stdin/stdout tests
"""
import sys
import os

# Add scripts directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import test-related functions
import re
from io import StringIO

# Copy key functions from eval.py for testing
def _generate_function_wrapper(code: str, fn_name: str, sample_input: str) -> str:
    """Generate function call wrapper"""
    input_lines = sample_input.strip().split('\n') if sample_input.strip() else []
    
    wrapper = f'''{code}

# ===== Auto-generated wrapper for function-style code =====
import sys as _sys

_input_data = _sys.stdin.read().strip()
_lines = _input_data.split('\\n') if _input_data else []
_line_idx = 0

def _read_line():
    global _line_idx
    if _line_idx < len(_lines):
        result = _lines[_line_idx]
        _line_idx += 1
        return result
    return ''

# Try calling function in multiple ways
_result = None
_called = False

# Strategy 1: Single integer
if not _called and len(_lines) == 1 and _lines[0].lstrip('-').isdigit():
    try:
        _arg = int(_lines[0])
        _result = {fn_name}(_arg)
        _called = True
    except:
        pass

# Strategy 2: First line is n, second line is array
if not _called and len(_lines) >= 2:
    try:
        _n = int(_lines[0])
        _arr = list(map(int, _lines[1].split()))
        try:
            _result = {fn_name}(_n, _arr)
            _called = True
        except TypeError:
            try:
                _result = {fn_name}(_arr)
                _called = True
            except:
                pass
    except:
        pass

# Strategy 3: Single line space-separated integers as list
if not _called and len(_lines) == 1:
    try:
        _arr = list(map(int, _lines[0].split()))
        _result = {fn_name}(_arr)
        _called = True
    except:
        pass

# Output result
if _result is not None:
    if isinstance(_result, list):
        if _result and isinstance(_result[0], list):
            for _row in _result:
                print(' '.join(map(str, _row)))
        else:
            print(' '.join(map(str, _result)))
    elif isinstance(_result, bool):
        print(str(_result).lower())
    else:
        print(_result)
'''
    return wrapper


def _adapt_code_for_stdin_test(code: str, inp: str) -> str:
    """Smart code style adaptation"""
    has_def = bool(re.search(r'\bdef\s+\w+\s*\(', code))
    has_input = bool(re.search(r'\binput\s*\(', code))
    has_print = bool(re.search(r'\bprint\s*\(', code))
    
    if has_input and has_print:
        return code
    if has_print and not has_def:
        return code
    
    if has_def and not has_input:
        solve_match = re.search(r'\bdef\s+(solve)\s*\(', code)
        if solve_match:
            fn_name = solve_match.group(1)
            return _generate_function_wrapper(code, fn_name, inp)
        
        top_level_funcs = re.findall(r'^def\s+(\w+)\s*\(', code, re.MULTILINE)
        if top_level_funcs:
            for func in top_level_funcs:
                if func not in ['main', 'test', 'helper', '__init__']:
                    return _generate_function_wrapper(code, func, inp)
    
    return code


def run_test(test_name, func_code, test_input, expected_output):
    """Run single test"""
    print(f"\n{'='*60}")
    print(f"Test: {test_name}")
    print(f"{'='*60}")
    
    # Adapt code
    adapted_code = _adapt_code_for_stdin_test(func_code, test_input)
    
    # Check if adaptation was performed
    if adapted_code != func_code:
        print("✓ Code adapted to stdin/stdout style")
    else:
        print("○ Code does not need adaptation")
    
    # Execute test
    inp = test_input if test_input.endswith('\n') else test_input + '\n'
    
    old_stdin, old_stdout = sys.stdin, sys.stdout
    try:
        sys.stdin = StringIO(inp)
        capture = StringIO()
        sys.stdout = capture
        exec(adapted_code, {})
    finally:
        sys.stdout, sys.stdin = old_stdout, old_stdin
    
    actual_output = capture.getvalue().strip()
    expected_clean = expected_output.strip()
    
    print(f"Input: {repr(test_input)}")
    print(f"Expected output: {repr(expected_clean)}")
    print(f"Actual output: {repr(actual_output)}")
    
    if actual_output == expected_clean:
        print("✅ Test passed!")
        return True
    else:
        print("❌ Test failed!")
        return False


# =============== Test Cases ===============

print("="*70)
print("Dual-Style Code Support Test")
print("="*70)

passed = 0
total = 0

# Test 1: Function-style code + single integer input
total += 1
result = run_test(
    "Function-style code + single integer input",
    func_code="""
def solve(n):
    cn5 = n * (n - 1) // 2 * (n - 2) // 3 * (n - 3) // 4 * (n - 4) // 5
    an5 = n * (n - 1) * (n - 2) * (n - 3) * (n - 4)
    return cn5 * an5
""",
    test_input="5",
    expected_output="120"
)
if result:
    passed += 1

# Test 2: Function-style code + array input  
total += 1
result = run_test(
    "Function-style code + array input",
    func_code="""
def solve(nums):
    return sum(nums)
""",
    test_input="1 2 3 4 5",
    expected_output="15"
)
if result:
    passed += 1

# Test 3: Script-style code (should not modify)
total += 1
result = run_test(
    "Script-style code (should not modify)",
    func_code="""
n = int(input())
print(n * 2)
""",
    test_input="10",
    expected_output="20"
)
if result:
    passed += 1

# Test 4: Function-style code + n and array input
total += 1
result = run_test(
    "Function-style code + n and array input",
    func_code="""
def solve(n, arr):
    return sum(arr[:n])
""",
    test_input="3\n1 2 3 4 5",
    expected_output="6"
)
if result:
    passed += 1

# Summary
print("\n" + "="*70)
print(f"Test Results: {passed}/{total} passed")
print("="*70)

if passed == total:
    print("✅ All tests passed! Dual-style support works correctly.")
else:
    print("⚠️ Some tests failed, need to check adaptation logic.")
