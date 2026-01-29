"""
Final diagnosis: Test evaluation flow with correct fields
"""
import json
import sys
import os

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, 'backend/scripts')
from eval import build_json_test_code, execute_code_safely

test_file = r'backend/storage/datasets/stage2 version2/test02-01.jsonl'

# Read first 20 problems
problems = []
with open(test_file, 'r', encoding='utf-8') as f:
    for i, line in enumerate(f):
        if i >= 20:
            break
        if line.strip():
            problems.append(json.loads(line))

print(f"Testing {len(problems)} problems")
print("="*60)

# Statistics
passed = 0
failed = 0
errors = {}

for idx, problem in enumerate(problems):
    task_id = problem.get('id', f'{idx}')
    tests = problem.get('tests', [])
    
    # Use correct field name: code instead of solution
    code = problem.get('code', '')
    
    if not code:
        print(f"[{idx+1}] {task_id}: No code field!")
        continue
    
    if not tests:
        print(f"[{idx+1}] {task_id}: No test cases!")
        continue
    
    # Detect test type
    is_stdin_stdout = False
    if isinstance(tests[0], str):
        try:
            test_obj = json.loads(tests[0])
            is_stdin_stdout = test_obj.get('type') == 'stdin_stdout'
        except:
            pass
    
    # Build test code
    test_code = build_json_test_code(tests[:3], code, max_tests=3)
    
    # Execute
    if is_stdin_stdout:
        result = execute_code_safely("", test_code, timeout=10)
    else:
        result = execute_code_safely(code, test_code, timeout=10)
    
    if result.passed:
        passed += 1
        print(f"[{idx+1}] {task_id}: PASS")
    else:
        failed += 1
        err_type = result.error_type.value
        errors[err_type] = errors.get(err_type, 0) + 1
        print(f"[{idx+1}] {task_id}: FAIL ({err_type})")
        # Show error details
        if failed <= 3:  # Only show details for first 3 errors
            print(f"    Error: {result.error_message[:200]}")

print()
print("="*60)
print(f"Result: {passed}/{passed+failed} passed ({100*passed/(passed+failed):.1f}%)")
print(f"Error classification: {errors}")
