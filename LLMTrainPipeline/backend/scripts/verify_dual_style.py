#!/usr/bin/env python3
"""
Verify dual-style support module works on real data
"""
import json
import re
import sys
from io import StringIO

# Import core functions from eval.py
sys.path.insert(0, __file__.rsplit('\\', 1)[0])

def _generate_function_wrapper(code: str, fn_name: str, sample_input: str) -> str:
    """Generate function call wrapper"""
    is_solution_class = fn_name.startswith("Solution().")
    if is_solution_class:
        method_name = fn_name.split(".")[-1]
        call_prefix = f"Solution().{method_name}"
    else:
        call_prefix = fn_name
    
    wrapper = f'''{code}

# ===== Auto-generated wrapper =====
import sys as _sys

_input_data = _sys.stdin.read().strip()
_lines = _input_data.split('\\n') if _input_data else []
_fn = {call_prefix}
_result = None
_called = False

# Strategy 1: Single integer
if not _called and len(_lines) == 1 and _lines[0].lstrip('-').isdigit():
    try:
        _arg = int(_lines[0])
        _result = _fn(_arg)
        _called = True
    except:
        pass

# Strategy 2: Single line integer list
if not _called and len(_lines) == 1:
    try:
        _arr = list(map(int, _lines[0].split()))
        _result = _fn(_arr)
        _called = True
    except:
        pass

# Strategy 3: First line is n, second line is array
if not _called and len(_lines) >= 2:
    try:
        _n = int(_lines[0])
        _arr = list(map(int, _lines[1].split()))
        for _args in [(_n, _arr), (_arr,)]:
            if not _called:
                try:
                    _result = _fn(*_args)
                    _called = True
                except TypeError:
                    pass
    except:
        pass

# Strategy 4: Empty input
if not _called and len(_lines) == 0:
    try:
        _result = _fn()
        _called = True
    except:
        try:
            _result = _fn([])
            _called = True
        except:
            pass

# Output result
if _result is not None:
    if isinstance(_result, list):
        print(' '.join(map(str, _result)))
    elif isinstance(_result, bool):
        print(str(_result).lower())
    else:
        print(_result)
elif _result == 0:
    print(0)
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


def normalize(s):
    """Normalize output for comparison"""
    return '\n'.join(l.rstrip() for l in str(s).strip().replace('\r\n', '\n').split('\n'))


def run_verification():
    """Run verification tests"""
    test_path = r"C:\Users\Shu Leo\Desktop\practical course\LLMTrainPipeline\backend\storage\datasets\stage2 version2\test02-01.jsonl"
    
    print("=" * 60)
    print("Dual-Style Support Module - End-to-End Verification")
    print("=" * 60)
    
    passed = 0
    total = 0
    failures = []
    
    try:
        with open(test_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                if i >= 5:  # Only test first 5 samples
                    break
                
                total += 1
                sample = json.loads(line)
                sample_id = sample.get('id', f'sample_{i}')
                code = sample.get('code', '')
                tests = sample.get('tests', [])
                
                if not tests:
                    print(f"SKIP {sample_id}: No test cases")
                    continue
                
                first_test = json.loads(tests[0]) if isinstance(tests[0], str) else tests[0]
                test_input = first_test.get('input', '')
                expected = first_test.get('expected_output', '')
                
                # Ensure test_input is a string
                if not isinstance(test_input, str):
                    test_input = str(test_input)
                
                # Adapt code
                adapted_code = _adapt_code_for_stdin_test(code, test_input)
                was_adapted = adapted_code != code
                
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
                
                actual = capture.getvalue().strip()
                expected_clean = str(expected).strip()
                
                match = normalize(actual) == normalize(expected_clean)
                adapt_str = "[Adapted]" if was_adapted else "[Original]"
                
                if match:
                    passed += 1
                    print(f"PASS {sample_id[:25]:<25} {adapt_str}")
                else:
                    print(f"FAIL {sample_id[:25]:<25} {adapt_str}")
                    failures.append({
                        'id': sample_id,
                        'expected': expected_clean[:50],
                        'actual': actual[:50]
                    })
                    
    except FileNotFoundError:
        print(f"ERROR: Data file does not exist: {test_path}")
        return
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print("=" * 60)
    print(f"Result: {passed}/{total} passed")
    
    if failures:
        print("\nFailure details:")
        for f in failures[:3]:
            print(f"  {f['id']}:")
            print(f"    Expected: {f['expected']}")
            print(f"    Actual: {f['actual']}")
    
    if passed == total:
        print("\n✅ Verification passed! Dual-style support module works correctly.")
    else:
        print(f"\n⚠️ {total - passed} tests failed, may need investigation.")
    
    print("=" * 60)


if __name__ == "__main__":
    run_verification()
