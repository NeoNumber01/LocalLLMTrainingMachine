#!/usr/bin/env python3
"""
Deep Test: Verify dual-style code support works correctly in various edge cases
Including real TACO data format tests
"""
import sys
import os
import json
import re
from io import StringIO

# =============== Copy key functions from eval.py ===============

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
if not _called and len(_lines) >= 1:
    try:
        if len(_lines) == 1 and _lines[0].lstrip('-').isdigit():
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

# Strategy 3: All lines as integer list
if not _called and len(_lines) >= 1:
    try:
        _all_ints = [int(line) for line in _lines if line.strip()]
        if len(_all_ints) == 1:
            _result = {fn_name}(_all_ints[0])
        else:
            _result = {fn_name}(_all_ints)
        _called = True
    except:
        pass

# Strategy 4: Single line space-separated integers
if not _called and len(_lines) == 1:
    try:
        _arr = list(map(int, _lines[0].split()))
        _result = {fn_name}(_arr)
        _called = True
    except:
        pass

# Strategy 5: String argument
if not _called and len(_lines) >= 1:
    try:
        if len(_lines) == 1:
            _result = {fn_name}(_lines[0])
        else:
            _result = {fn_name}(_lines)
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
    has_class = bool(re.search(r'\bclass\s+\w+', code))
    
    if has_input and has_print:
        return code
    if has_print and not has_def:
        return code
    
    if has_def and not has_input:
        fn_name = None
        
        # Prioritize solve function
        solve_match = re.search(r'\bdef\s+(solve)\s*\(', code)
        if solve_match:
            fn_name = solve_match.group(1)
        else:
            # Find Solution class methods
            if has_class:
                method_match = re.search(r'\bclass\s+Solution\b.*?\bdef\s+(\w+)\s*\(self', code, re.DOTALL)
                if method_match and method_match.group(1) != '__init__':
                    fn_name = f"Solution().{method_match.group(1)}"
            
            # Find any top-level function
            if not fn_name:
                top_level_funcs = re.findall(r'^def\s+(\w+)\s*\(', code, re.MULTILINE)
                if top_level_funcs:
                    for func in top_level_funcs:
                        if func not in ['main', 'test', 'helper', '__init__']:
                            fn_name = func
                            break
                    if not fn_name:
                        fn_name = top_level_funcs[0]
        
        if fn_name:
            return _generate_function_wrapper(code, fn_name, inp)
    
    return code


def run_test(test_name, func_code, test_input, expected_output, should_adapt=True):
    """Run single test"""
    print(f"\n{'='*60}")
    print(f"Test: {test_name}")
    print(f"{'='*60}")
    
    try:
        # Adapt code
        adapted_code = _adapt_code_for_stdin_test(func_code, test_input)
        
        # Check if adaptation was performed
        was_adapted = adapted_code != func_code
        if was_adapted:
            if should_adapt:
                print("✓ Code adapted to stdin/stdout style")
            else:
                print("⚠️ Unexpected adaptation (should not happen)")
        else:
            if should_adapt:
                print("⚠️ Code was not adapted (might be a problem)")
            else:
                print("✓ Code correctly kept as-is")
        
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
        
        print(f"Input: {repr(test_input[:50])}{'...' if len(test_input) > 50 else ''}")
        print(f"Expected: {repr(expected_clean[:50])}{'...' if len(expected_clean) > 50 else ''}")
        print(f"Actual: {repr(actual_output[:50])}{'...' if len(actual_output) > 50 else ''}")
        
        if actual_output == expected_clean:
            print("✅ Test passed!")
            return True
        else:
            print("❌ Test failed!")
            return False
            
    except Exception as e:
        print(f"❌ Execution error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


# =============== Test Cases ===============

print("="*70)
print("Dual-Style Code Support - Deep Test")
print("="*70)

passed = 0
total = 0

# Test 1: Real TACO format data - taco_0_sol0
total += 1
result = run_test(
    "Real TACO data: taco_0_sol0 (benches problem)",
    func_code="""
def solve(n):
    cn5 = n * (n - 1) // 2 * (n - 2) // 3 * (n - 3) // 4 * (n - 4) // 5
    an5 = n * (n - 1) * (n - 2) * (n - 3) * (n - 4)
    return cn5 * an5
""",
    test_input="5",
    expected_output="120"
)
if result: passed += 1

# Test 2: Solution class method
total += 1
result = run_test(
    "Solution class method (LeetCode style)",
    func_code="""
class Solution:
    def getMaxandMinProduct(self, A, Q, N, M):
        from collections import Counter
        s, m = Counter(A), max(A)
        ans = [0] * len(Q)
        for i, e in enumerate(Q):
            if e != 0:
                for k in range(e, m + 1, e):
                    ans[i] += s.get(k, 0)
        return ans
""",
    test_input="5\n1 2 3 4 5\n3\n1 2 3",
    expected_output="5 3 2"  # Example expected output
)
if result: passed += 1

# Test 3: Code with helper functions
total += 1
result = run_test(
    "Code with helper functions",
    func_code="""
def helper(x):
    return x * 2

def solve(n):
    return helper(n) + 1
""",
    test_input="5",
    expected_output="11"
)
if result: passed += 1

# Test 4: Script-style code with input/print (should not modify)
total += 1
result = run_test(
    "Script-style code (should not modify)",
    func_code="""
n = int(input())
cn5 = n * (n - 1) // 2 * (n - 2) // 3 * (n - 3) // 4 * (n - 4) // 5
an5 = n * (n - 1) * (n - 2) * (n - 3) * (n - 4)
print(cn5 * an5)
""",
    test_input="5",
    expected_output="120",
    should_adapt=False
)
if result: passed += 1

# Test 5: Mixed style code (has function definition and input/print)
total += 1
result = run_test(
    "Mixed style code (has def and input/print)",
    func_code="""
def solve(n):
    cn5 = n * (n - 1) // 2 * (n - 2) // 3 * (n - 3) // 4 * (n - 4) // 5
    an5 = n * (n - 1) * (n - 2) * (n - 3) * (n - 4)
    return cn5 * an5

n = int(input())
print(solve(n))
""",
    test_input="5",
    expected_output="120",
    should_adapt=False
)
if result: passed += 1

# Test 6: Empty input handling
total += 1
result = run_test(
    "Empty array handling",
    func_code="""
def solve(nums):
    if not nums:
        return 0
    return sum(nums)
""",
    test_input="",
    expected_output="0"
)
if result: passed += 1

# Test 7: Multi-line complex input
total += 1
result = run_test(
    "Multi-line complex input (n + array)",
    func_code="""
def solve(n, arr):
    return max(arr) if arr else 0
""",
    test_input="5\n3 1 4 1 5",
    expected_output="5"
)
if result: passed += 1

# Test 8: Return list
total += 1
result = run_test(
    "Return list",
    func_code="""
def solve(nums):
    return sorted(nums)
""",
    test_input="5 3 1 4 2",
    expected_output="1 2 3 4 5"
)
if result: passed += 1

# Test 9: Boolean return value
total += 1
result = run_test(
    "Boolean return value",
    func_code="""
def solve(n):
    return n > 0
""",
    test_input="5",
    expected_output="true"
)
if result: passed += 1

# Test 10: Non-solve function name
total += 1
result = run_test(
    "Non-solve function name (getMaxandMinProduct)",
    func_code="""
def getMaxandMinProduct(A, Q, N, M):
    from collections import Counter
    s, m = Counter(A), max(A) if A else 0
    return sum(s.values())
""",
    test_input="5\n1 2 3 4 5",
    expected_output="5"
)
if result: passed += 1

# Summary
print("\n" + "="*70)
print(f"Test Results: {passed}/{total} passed")
print("="*70)

if passed == total:
    print("✅ All tests passed!")
elif passed >= total * 0.7:
    print(f"⚠️ Most tests passed ({passed}/{total}), some edge cases may need handling")
else:
    print(f"❌ Multiple tests failed ({passed}/{total}), needs fixing")

# =============== Real TACO Data Test ===============
print("\n" + "="*70)
print("Real TACO Dataset Test")
print("="*70)

train_path = r"C:\Users\Shu Leo\Desktop\practical course\LLMTrainPipeline\backend\storage\datasets\stage2 version2\train02-01.jsonl"
test_path = r"C:\Users\Shu Leo\Desktop\practical course\LLMTrainPipeline\backend\storage\datasets\stage2 version2\test02-01.jsonl"

try:
    # Get one function-style sample from training set
    with open(train_path, 'r', encoding='utf-8') as f:
        train_sample = json.loads(f.readline())
    
    # Get one stdin/stdout sample from test set
    with open(test_path, 'r', encoding='utf-8') as f:
        test_sample = json.loads(f.readline())
    
    print(f"\nTraining sample: {train_sample['id']}")
    print(f"Test sample: {test_sample['id']}")
    
    # Use training sample code style + test sample test cases
    train_code = train_sample['code']
    test_tests = test_sample['tests']
    
    if test_tests:
        first_test = json.loads(test_tests[0]) if isinstance(test_tests[0], str) else test_tests[0]
        test_input = first_test.get('input', '')
        expected = first_test.get('expected_output', '')
        
        print(f"\nSimulated scenario: Using reference code + stdin/stdout test")
        print(f"Input: {test_input[:50]}...")
        print(f"Expected: {expected[:50]}...")
        
        # Test adaptation
        adapted = _adapt_code_for_stdin_test(test_sample['code'], test_input)
        
        old_stdin, old_stdout = sys.stdin, sys.stdout
        inp = test_input if test_input.endswith('\n') else test_input + '\n'
        try:
            sys.stdin = StringIO(inp)
            capture = StringIO()
            sys.stdout = capture
            exec(adapted, {})
        finally:
            sys.stdout, sys.stdin = old_stdout, old_stdin
        
        actual = capture.getvalue().strip()
        
        # Normalized comparison
        def normalize(s):
            return '\n'.join(l.rstrip() for l in str(s).strip().replace('\r\n', '\n').split('\n'))
        
        if normalize(actual) == normalize(expected):
            print("✅ Real data test passed!")
        else:
            print(f"❌ Real data test failed")
            print(f"  Actual output: {actual[:100]}")
            print(f"  Expected output: {expected[:100]}")
            
except FileNotFoundError as e:
    print(f"⚠️ Data file does not exist: {e}")
except Exception as e:
    print(f"❌ Test error: {e}")
    import traceback
    traceback.print_exc()
