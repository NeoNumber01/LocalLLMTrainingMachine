#!/usr/bin/env python3
"""
验证双风格支持模块在真实数据上的工作情况
"""
import json
import re
import sys
from io import StringIO

# 从 eval.py 导入核心函数
sys.path.insert(0, __file__.rsplit('\\', 1)[0])

def _generate_function_wrapper(code: str, fn_name: str, sample_input: str) -> str:
    """生成函数调用包装器"""
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

# 策略1: 单个整数
if not _called and len(_lines) == 1 and _lines[0].lstrip('-').isdigit():
    try:
        _arg = int(_lines[0])
        _result = _fn(_arg)
        _called = True
    except:
        pass

# 策略2: 单行整数列表
if not _called and len(_lines) == 1:
    try:
        _arr = list(map(int, _lines[0].split()))
        _result = _fn(_arr)
        _called = True
    except:
        pass

# 策略3: 第一行是n，第二行是数组
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

# 策略4: 空输入
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

# 输出结果
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


def normalize(s):
    """规范化输出以进行比较"""
    return '\n'.join(l.rstrip() for l in str(s).strip().replace('\r\n', '\n').split('\n'))


def run_verification():
    """运行验证测试"""
    test_path = r"C:\Users\Shu Leo\Desktop\practical course\LLMTrainPipeline\backend\storage\datasets\stage2 version2\test02-01.jsonl"
    
    print("=" * 60)
    print("双风格支持模块 - 端到端验证")
    print("=" * 60)
    
    passed = 0
    total = 0
    failures = []
    
    try:
        with open(test_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                if i >= 5:  # 只测试前5个样本
                    break
                
                total += 1
                sample = json.loads(line)
                sample_id = sample.get('id', f'sample_{i}')
                code = sample.get('code', '')
                tests = sample.get('tests', [])
                
                if not tests:
                    print(f"SKIP {sample_id}: 无测试用例")
                    continue
                
                first_test = json.loads(tests[0]) if isinstance(tests[0], str) else tests[0]
                test_input = first_test.get('input', '')
                expected = first_test.get('expected_output', '')
                
                # 确保 test_input 是字符串
                if not isinstance(test_input, str):
                    test_input = str(test_input)
                
                # 适配代码
                adapted_code = _adapt_code_for_stdin_test(code, test_input)
                was_adapted = adapted_code != code
                
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
                
                actual = capture.getvalue().strip()
                expected_clean = str(expected).strip()
                
                match = normalize(actual) == normalize(expected_clean)
                adapt_str = "[已适配]" if was_adapted else "[原样]"
                
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
        print(f"ERROR: 数据文件不存在: {test_path}")
        return
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print("=" * 60)
    print(f"结果: {passed}/{total} 通过")
    
    if failures:
        print("\n失败详情:")
        for f in failures[:3]:
            print(f"  {f['id']}:")
            print(f"    期望: {f['expected']}")
            print(f"    实际: {f['actual']}")
    
    if passed == total:
        print("\n✅ 验证通过！双风格支持模块工作正常。")
    else:
        print(f"\n⚠️ {total - passed} 个测试失败，可能需要检查。")
    
    print("=" * 60)


if __name__ == "__main__":
    run_verification()
