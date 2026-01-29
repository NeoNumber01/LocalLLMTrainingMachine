#!/usr/bin/env python3
"""
深度测试：验证双风格代码支持在各种边界情况下的正确性
包括真实 TACO 数据格式测试
"""
import sys
import os
import json
import re
from io import StringIO

# =============== 从 eval.py 复制关键函数 ===============

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
if not _called and len(_lines) >= 1:
    try:
        if len(_lines) == 1 and _lines[0].lstrip('-').isdigit():
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

# 策略3: 所有行作为整数列表
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

# 策略4: 单行空格分隔的整数
if not _called and len(_lines) == 1:
    try:
        _arr = list(map(int, _lines[0].split()))
        _result = {fn_name}(_arr)
        _called = True
    except:
        pass

# 策略5: 字符串参数
if not _called and len(_lines) >= 1:
    try:
        if len(_lines) == 1:
            _result = {fn_name}(_lines[0])
        else:
            _result = {fn_name}(_lines)
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
    has_class = bool(re.search(r'\bclass\s+\w+', code))
    
    if has_input and has_print:
        return code
    if has_print and not has_def:
        return code
    
    if has_def and not has_input:
        fn_name = None
        
        # 优先查找 solve 函数
        solve_match = re.search(r'\bdef\s+(solve)\s*\(', code)
        if solve_match:
            fn_name = solve_match.group(1)
        else:
            # 查找 Solution 类的方法
            if has_class:
                method_match = re.search(r'\bclass\s+Solution\b.*?\bdef\s+(\w+)\s*\(self', code, re.DOTALL)
                if method_match and method_match.group(1) != '__init__':
                    fn_name = f"Solution().{method_match.group(1)}"
            
            # 查找任意顶层函数
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
    """运行单个测试"""
    print(f"\n{'='*60}")
    print(f"测试: {test_name}")
    print(f"{'='*60}")
    
    try:
        # 适配代码
        adapted_code = _adapt_code_for_stdin_test(func_code, test_input)
        
        # 检测是否进行了适配
        was_adapted = adapted_code != func_code
        if was_adapted:
            if should_adapt:
                print("✓ 代码已适配为 stdin/stdout 风格")
            else:
                print("⚠️ 意外进行了适配（不应该发生）")
        else:
            if should_adapt:
                print("⚠️ 代码未被适配（可能是问题）")
            else:
                print("✓ 代码正确保持原样")
        
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
        
        print(f"输入: {repr(test_input[:50])}{'...' if len(test_input) > 50 else ''}")
        print(f"期望: {repr(expected_clean[:50])}{'...' if len(expected_clean) > 50 else ''}")
        print(f"实际: {repr(actual_output[:50])}{'...' if len(actual_output) > 50 else ''}")
        
        if actual_output == expected_clean:
            print("✅ 测试通过!")
            return True
        else:
            print("❌ 测试失败!")
            return False
            
    except Exception as e:
        print(f"❌ 执行错误: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


# =============== 测试用例 ===============

print("="*70)
print("双风格代码支持 - 深度测试")
print("="*70)

passed = 0
total = 0

# 测试1: 真实 TACO 格式数据 - taco_0_sol0
total += 1
result = run_test(
    "真实TACO数据: taco_0_sol0 (benches问题)",
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

# 测试2: Solution 类方法
total += 1
result = run_test(
    "Solution类方法 (LeetCode风格)",
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
    expected_output="5 3 2"  # 示例期望输出
)
if result: passed += 1

# 测试3: 带辅助函数的代码
total += 1
result = run_test(
    "带辅助函数的代码",
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

# 测试4: 已有 input/print 的脚本式代码（不应修改）
total += 1
result = run_test(
    "脚本式代码（不应修改）",
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

# 测试5: 混合风格代码（有函数定义，也有 input/print）
total += 1
result = run_test(
    "混合风格代码（有def也有input/print）",
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

# 测试6: 空输入处理
total += 1
result = run_test(
    "空数组处理",
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

# 测试7: 多行复杂输入
total += 1
result = run_test(
    "多行复杂输入 (n + 数组)",
    func_code="""
def solve(n, arr):
    return max(arr) if arr else 0
""",
    test_input="5\n3 1 4 1 5",
    expected_output="5"
)
if result: passed += 1

# 测试8: 返回列表
total += 1
result = run_test(
    "返回列表",
    func_code="""
def solve(nums):
    return sorted(nums)
""",
    test_input="5 3 1 4 2",
    expected_output="1 2 3 4 5"
)
if result: passed += 1

# 测试9: 布尔返回值
total += 1
result = run_test(
    "布尔返回值",
    func_code="""
def solve(n):
    return n > 0
""",
    test_input="5",
    expected_output="true"
)
if result: passed += 1

# 测试10: 非 solve 函数名
total += 1
result = run_test(
    "非 solve 函数名 (getMaxandMinProduct)",
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

# 汇总
print("\n" + "="*70)
print(f"测试结果: {passed}/{total} 通过")
print("="*70)

if passed == total:
    print("✅ 所有测试通过！")
elif passed >= total * 0.7:
    print(f"⚠️ 大部分测试通过 ({passed}/{total})，部分边界情况可能需要处理")
else:
    print(f"❌ 多个测试失败 ({passed}/{total})，需要修复")

# =============== 真实 TACO 数据测试 ===============
print("\n" + "="*70)
print("真实 TACO 数据集测试")
print("="*70)

train_path = r"C:\Users\Shu Leo\Desktop\practical course\LLMTrainPipeline\backend\storage\datasets\stage2 version2\train02-01.jsonl"
test_path = r"C:\Users\Shu Leo\Desktop\practical course\LLMTrainPipeline\backend\storage\datasets\stage2 version2\test02-01.jsonl"

try:
    # 从训练集取一个函数式样本
    with open(train_path, 'r', encoding='utf-8') as f:
        train_sample = json.loads(f.readline())
    
    # 从测试集取一个 stdin/stdout 样本
    with open(test_path, 'r', encoding='utf-8') as f:
        test_sample = json.loads(f.readline())
    
    print(f"\n训练样本: {train_sample['id']}")
    print(f"测试样本: {test_sample['id']}")
    
    # 用训练样本的代码风格 + 测试样本的测试用例
    train_code = train_sample['code']
    test_tests = test_sample['tests']
    
    if test_tests:
        first_test = json.loads(test_tests[0]) if isinstance(test_tests[0], str) else test_tests[0]
        test_input = first_test.get('input', '')
        expected = first_test.get('expected_output', '')
        
        print(f"\n模拟场景: 使用参考代码 + stdin/stdout 测试")
        print(f"输入: {test_input[:50]}...")
        print(f"期望: {expected[:50]}...")
        
        # 测试适配
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
        
        # 规范化比较
        def normalize(s):
            return '\n'.join(l.rstrip() for l in str(s).strip().replace('\r\n', '\n').split('\n'))
        
        if normalize(actual) == normalize(expected):
            print("✅ 真实数据测试通过!")
        else:
            print(f"❌ 真实数据测试失败")
            print(f"  实际输出: {actual[:100]}")
            print(f"  期望输出: {expected[:100]}")
            
except FileNotFoundError as e:
    print(f"⚠️ 数据文件不存在: {e}")
except Exception as e:
    print(f"❌ 测试出错: {e}")
    import traceback
    traceback.print_exc()
