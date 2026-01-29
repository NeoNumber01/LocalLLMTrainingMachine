#!/usr/bin/env python3
"""
测试脚本：验证双风格代码支持
测试函数式代码能否在 stdin/stdout 测试中正确执行
"""
import sys
import os

# 添加 scripts 目录到 path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入测试相关函数
import re
from io import StringIO

# 从 eval.py 复制关键函数进行测试
def _generate_function_wrapper(code: str, fn_name: str, sample_input: str) -> str:
    """生成函数调用包装器"""
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

# 尝试以多种方式调用函数
_result = None
_called = False

# 策略1: 单个整数
if not _called and len(_lines) == 1 and _lines[0].lstrip('-').isdigit():
    try:
        _arg = int(_lines[0])
        _result = {fn_name}(_arg)
        _called = True
    except:
        pass

# 策略2: 第一行是n，第二行是数组
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

# 策略3: 单行空格分隔的整数作为列表
if not _called and len(_lines) == 1:
    try:
        _arr = list(map(int, _lines[0].split()))
        _result = {fn_name}(_arr)
        _called = True
    except:
        pass

# 输出结果
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
    """智能适配代码风格"""
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
    """运行单个测试"""
    print(f"\n{'='*60}")
    print(f"测试: {test_name}")
    print(f"{'='*60}")
    
    # 适配代码
    adapted_code = _adapt_code_for_stdin_test(func_code, test_input)
    
    # 检测是否进行了适配
    if adapted_code != func_code:
        print("✓ 代码已适配为 stdin/stdout 风格")
    else:
        print("○ 代码无需适配")
    
    # 执行测试
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
    
    print(f"输入: {repr(test_input)}")
    print(f"期望输出: {repr(expected_clean)}")
    print(f"实际输出: {repr(actual_output)}")
    
    if actual_output == expected_clean:
        print("✅ 测试通过!")
        return True
    else:
        print("❌ 测试失败!")
        return False


# =============== 测试用例 ===============

print("="*70)
print("双风格代码支持测试")
print("="*70)

passed = 0
total = 0

# 测试1: 函数式代码 + 单个整数输入
total += 1
result = run_test(
    "函数式代码 + 单个整数输入",
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

# 测试2: 函数式代码 + 数组输入  
total += 1
result = run_test(
    "函数式代码 + 数组输入",
    func_code="""
def solve(nums):
    return sum(nums)
""",
    test_input="1 2 3 4 5",
    expected_output="15"
)
if result:
    passed += 1

# 测试3: 脚本式代码（不应修改）
total += 1
result = run_test(
    "脚本式代码（不应修改）",
    func_code="""
n = int(input())
print(n * 2)
""",
    test_input="10",
    expected_output="20"
)
if result:
    passed += 1

# 测试4: 函数式代码 + n和数组输入
total += 1
result = run_test(
    "函数式代码 + n和数组输入",
    func_code="""
def solve(n, arr):
    return sum(arr[:n])
""",
    test_input="3\n1 2 3 4 5",
    expected_output="6"
)
if result:
    passed += 1

# 汇总
print("\n" + "="*70)
print(f"测试结果: {passed}/{total} 通过")
print("="*70)

if passed == total:
    print("✅ 所有测试通过！双风格支持工作正常。")
else:
    print("⚠️ 部分测试失败，需要检查适配逻辑。")
