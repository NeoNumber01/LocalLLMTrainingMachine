"""
最终诊断：用正确的字段测试评测流程
"""
import json
import sys
import os

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, 'backend/scripts')
from eval import build_json_test_code, execute_code_safely

test_file = r'backend/storage/datasets/stage2 version2/test02-01.jsonl'

# 读取前20个问题
problems = []
with open(test_file, 'r', encoding='utf-8') as f:
    for i, line in enumerate(f):
        if i >= 20:
            break
        if line.strip():
            problems.append(json.loads(line))

print(f"测试 {len(problems)} 个问题")
print("="*60)

# 统计
passed = 0
failed = 0
errors = {}

for idx, problem in enumerate(problems):
    task_id = problem.get('id', f'{idx}')
    tests = problem.get('tests', [])
    
    # 使用正确的字段名: code 而不是 solution
    code = problem.get('code', '')
    
    if not code:
        print(f"[{idx+1}] {task_id}: 没有代码字段!")
        continue
    
    if not tests:
        print(f"[{idx+1}] {task_id}: 没有测试用例!")
        continue
    
    # 检测测试类型
    is_stdin_stdout = False
    if isinstance(tests[0], str):
        try:
            test_obj = json.loads(tests[0])
            is_stdin_stdout = test_obj.get('type') == 'stdin_stdout'
        except:
            pass
    
    # 构建测试代码
    test_code = build_json_test_code(tests[:3], code, max_tests=3)
    
    # 执行
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
        # 显示错误详情
        if failed <= 3:  # 只显示前3个错误的详情
            print(f"    错误: {result.error_message[:200]}")

print()
print("="*60)
print(f"结果: {passed}/{passed+failed} 通过 ({100*passed/(passed+failed):.1f}%)")
print(f"错误分类: {errors}")
