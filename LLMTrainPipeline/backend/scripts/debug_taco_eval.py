#!/usr/bin/env python3
"""
Quick debug script to test TACO format evaluation logic.
This simulates what eval.py does for a single TACO problem.
"""

import json
import sys
import os

# Add scripts directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load a sample from TACO test dataset
dataset_path = r"C:\Users\Shu Leo\Desktop\practical course\LLMTrainPipeline\backend\storage\datasets\stage2 version2\test02-01.jsonl"

print("=== Loading first sample from dataset ===")
with open(dataset_path, 'r', encoding='utf-8') as f:
    first_line = f.readline()
    problem = json.loads(first_line)

print(f"ID: {problem['id']}")
print(f"Source: {problem.get('source', 'unknown')}")
print(f"Difficulty: {problem.get('difficulty', 'unknown')}")
print(f"Prompt length: {len(problem.get('prompt', ''))}")
print(f"Code length: {len(problem.get('code', ''))}")
print(f"Number of tests: {len(problem.get('tests', []))}")
print()

# Get the fields
instruction = problem.get('instruction', problem.get('prompt', ''))
code = problem.get('code', '')  # This is the reference solution
tests_list = problem.get('tests', [])

print("=== Prompt Preview (first 500 chars) ===")
print(instruction[:500])
print()

print("=== Reference Code ===")
print(code)
print()

print("=== First Test ===")
if tests_list:
    first_test = tests_list[0]
    if isinstance(first_test, str):
        print(first_test)
    else:
        print(json.dumps(first_test, indent=2))
print()

# Test if tests are stdin_stdout type
is_stdin_stdout = False
if tests_list and isinstance(tests_list[0], str):
    first_test_str = tests_list[0].strip()
    if first_test_str.startswith('{'):
        try:
            test_obj = json.loads(first_test_str)
            is_stdin_stdout = (
                test_obj.get('type') == 'stdin_stdout' or 
                (not test_obj.get('fn_name') and 'input' in test_obj and 'expected_output' in test_obj)
            )
            print(f"Test type: {'stdin_stdout' if is_stdin_stdout else 'function_call'}")
        except json.JSONDecodeError:
            print("Failed to parse test JSON")

print()
print("=== Simulating test code generation ===")

def _convert_stdin_test_enhanced(inp: str, exp: str, code: str, idx: int) -> str:
    """Convert stdin_stdout test to executable code (enhanced version)."""
    # 确保输入以换行结尾
    if inp and not inp.endswith('\n'):
        inp += '\n'
    
    # 处理列表形式的输出  
    if isinstance(exp, list):
        exp = '\n'.join(str(e) for e in exp)
    
    return f'''
# Test {idx}
import sys
from io import StringIO
_i{idx}={repr(inp)}
_e{idx}={repr(str(exp))}
_si{idx},_so{idx}=sys.stdin,sys.stdout
try:
    sys.stdin=StringIO(_i{idx})
    _c{idx}=StringIO()
    sys.stdout=_c{idx}
    exec({repr(code)},{{}})
finally:
    sys.stdout,sys.stdin=_so{idx},_si{idx}
_o{idx}=_c{idx}.getvalue()
def _n{idx}(s):return'\\n'.join(l.rstrip()for l in str(s).strip().replace('\\r\\n','\\n').split('\\n'))
assert _n{idx}(_o{idx})==_n{idx}(_e{idx}),f"Test {idx} failed: got {{repr(_o{idx}[:100])}} expected {{repr(_e{idx}[:100])}}"
'''


def build_json_test_code(tests_raw: list, solution_code: str, max_tests: int = 5) -> str:
    """Build executable test code from test list."""
    if not tests_raw:
        return ""
    
    test_codes = []
    for i, t in enumerate(tests_raw[:max_tests]):
        if isinstance(t, str):
            t = t.strip()
            if t.startswith('{'):
                test = json.loads(t)
                inp = test.get('input', '')
                exp = test.get('expected_output', '')
                test_codes.append(_convert_stdin_test_enhanced(inp, exp, solution_code, i))
    
    return '\n'.join(test_codes)


# Build test code using reference solution
test_code = build_json_test_code(tests_list, code, max_tests=3)
print("Generated test code:")
print(test_code[:2000] + "..." if len(test_code) > 2000 else test_code)
print()

print("=== Running test with REFERENCE solution ===")
try:
    exec(test_code)
    print("✓ All tests passed with reference solution!")
except AssertionError as e:
    print(f"✗ AssertionError: {e}")
except Exception as e:
    print(f"✗ Error: {type(e).__name__}: {e}")

print()
print("=== CRITICAL ISSUE ANALYSIS ===")
print("""
The test generation logic works correctly with the REFERENCE solution.
If model-generated code fails all tests, possible causes are:

1. **Model output doesn't match stdin/stdout format**
   - Model may be generating function-style code instead of script-style
   - e.g., generating 'def solve(n)' instead of 'n = int(input())'

2. **Code extraction fails**
   - The model output may include explanations that aren't stripped properly
   - Markdown code blocks may not be extracted correctly

3. **Prompt doesn't indicate stdin/stdout style clearly enough**
   - The prompt asks for stdin/stdout but model doesn't understand

4. **Speed issue: Every sample requires model inference**
   - 863 problems × 10 samples = 8630 model inferences!
   - This will take HOURS on a single GPU
""")

print()
print("=== RECOMMENDATION ===")
print("""
To debug further, you should:
1. Run eval on just 1-2 problems first to see actual model output
2. Check if the model is generating stdin/stdout style code
3. Consider adding eval mode to skip model inference and use reference code
""")
