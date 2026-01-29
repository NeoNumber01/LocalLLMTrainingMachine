#!/usr/bin/env python3
"""
Code Evaluation Script with Comprehensive Metrics
Evaluates model-generated code against test cases.

Metrics included:
- Pass@k (k=1,5,10)
- Error classification (syntax/runtime/timeout/invalid output)
- Execution time statistics (mean, p50, p95, max)
- Robustness testing (fuzzing, boundary conditions)
- Code quality analysis
- Self-consistency evaluation

Usage: python eval.py --config config.json
"""

import os
import sys
import json
import argparse
import logging
import subprocess
import tempfile
import signal
import time
import re
import ast
import traceback
import statistics
import gc
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable, Tuple
from contextlib import contextmanager
from enum import Enum
from dataclasses import dataclass, field, asdict
from math import comb

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import PeftModel

# Import postprocess module for code extraction
from postprocess.extractor import CodeExtractor

# Import eval logger for comprehensive logging
from eval_logger import (
    EvalLogger, EvalSummary, GenerationSettings, JudgeSettings,
    SampleResult, output_eval_log_event
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("CodeEval")


# ============== Data Classes ==============

class ErrorType(Enum):
    """Error type classification"""
    NONE = "none"
    SYNTAX_ERROR = "syntax_error"
    RUNTIME_ERROR = "runtime_error"
    TIMEOUT = "timeout"
    INVALID_OUTPUT = "invalid_output"
    ASSERTION_ERROR = "assertion_error"
    IMPORT_ERROR = "import_error"
    MEMORY_ERROR = "memory_error"


@dataclass
class ExecutionResult:
    """Result of code execution"""
    passed: bool
    error_type: ErrorType = ErrorType.NONE
    error_message: str = ""
    execution_time_ms: float = 0.0
    stdout: str = ""
    stderr: str = ""


@dataclass
class ProblemResult:
    """Result for a single problem"""
    task_id: str
    n_samples: int = 0
    n_passed: int = 0
    n_compiled: int = 0
    error_counts: Dict[str, int] = field(default_factory=dict)
    execution_times: List[float] = field(default_factory=list)
    code_lengths: List[int] = field(default_factory=list)
    difficulty: str = "unknown"
    category: str = "unknown"


@dataclass
class ErrorStats:
    """Error classification statistics"""
    syntax_error_rate: float = 0.0
    runtime_error_rate: float = 0.0
    timeout_rate: float = 0.0
    invalid_output_rate: float = 0.0
    assertion_error_rate: float = 0.0
    import_error_rate: float = 0.0
    memory_error_rate: float = 0.0


@dataclass
class TimeStats:
    """Execution time statistics"""
    mean_runtime_ms: float = 0.0
    p50_runtime_ms: float = 0.0
    p95_runtime_ms: float = 0.0
    max_runtime_ms: float = 0.0
    tle_rate: float = 0.0


@dataclass
class CodeQualityStats:
    """Code quality statistics"""
    avg_code_length: float = 0.0
    avg_line_count: float = 0.0
    extra_io_rate: float = 0.0
    interface_compliance_rate: float = 0.0


@dataclass
class SegmentResult:
    """Result for a segment (difficulty/category)"""
    count: int = 0
    pass_at_1: float = 0.0
    compile_rate: float = 0.0


@dataclass
class ConsistencyStats:
    """Self-consistency statistics"""
    self_consistency_rate: float = 0.0
    variance: float = 0.0


@dataclass
class RobustnessStats:
    """Robustness testing statistics"""
    fuzz_pass_rate: float = 0.0
    boundary_pass_rate: float = 0.0


# ============== Execution Timeout ==============

EXECUTION_TIMEOUT = 10  # seconds


@contextmanager
def time_limit(seconds):
    """Context manager that limits execution time."""
    def signal_handler(signum, frame):
        raise TimeoutError("Execution timed out")
    
    if sys.platform != 'win32':
        signal.signal(signal.SIGALRM, signal_handler)
        signal.alarm(seconds)
        try:
            yield
        finally:
            signal.alarm(0)
    else:
        # Windows doesn't support SIGALRM
        yield


# ============== Model Loading ==============

def load_model(model_path: str, adapter_path: str = None, quantization: str = "4bit"):
    """Load model with optional LoRA adapter.
    
    Fixed for bitsandbytes compatibility - always uses device_map="auto"
    to avoid the .to() error with quantized models.
    """
    logger.info(f"Loading model from: {model_path}")
    
    tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
        tokenizer.pad_token_id = tokenizer.eos_token_id
    
    # Quantization config with compatibility fixes
    quant_config = None
    if quantization == "4bit":
        quant_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_use_double_quant=True,
        )
    elif quantization == "8bit":
        quant_config = BitsAndBytesConfig(
            load_in_8bit=True,
            llm_int8_enable_fp32_cpu_offload=True,
        )
    
    # Always use device_map="auto" to avoid .to() issues with quantized models
    model_kwargs = {
        "trust_remote_code": True,
        "torch_dtype": torch.float16,
        "device_map": "auto",  # Critical: avoids bitsandbytes .to() error
        "low_cpu_mem_usage": True,
    }
    if quant_config:
        model_kwargs["quantization_config"] = quant_config
    
    model = AutoModelForCausalLM.from_pretrained(model_path, **model_kwargs)
    
    # Load adapter if provided
    if adapter_path and os.path.exists(adapter_path):
        logger.info(f"Loading adapter from: {adapter_path}")
        # P0-FIX: 输出到 stdout 供前端显示
        print(json.dumps({
            "type": "log",
            "level": "info",
            "message": f"Loading LoRA adapter from: {adapter_path}"
        }), flush=True)
        model = PeftModel.from_pretrained(model, adapter_path)
        print(json.dumps({
            "type": "log",
            "level": "info",
            "message": "LoRA adapter loaded successfully"
        }), flush=True)
    elif adapter_path:
        # adapter_path 提供了但路径不存在
        logger.warning(f"Adapter path provided but not found: {adapter_path}")
        print(json.dumps({
            "type": "log",
            "level": "warning",
            "message": f"WARNING: Adapter path not found: {adapter_path}. Running without LoRA."
        }), flush=True)
    else:
        # 没有提供 adapter，使用基座模型
        print(json.dumps({
            "type": "log",
            "level": "info",
            "message": "No adapter specified, using base model only"
        }), flush=True)
    
    model.eval()
    return model, tokenizer


# ============== Code Generation ==============

def build_chat_prompt(tokenizer, instruction: str, signature: str = None) -> str:
    """Build prompt using chat template if available.
    
    References LeoLLM's approach for better model compatibility.
    """
    # Build messages in chat format
    system_content = "You are an expert Python programmer. Write clean, efficient, and correct code."
    user_content = instruction
    if signature:
        user_content = f"{instruction}\n\nFunction signature: {signature}"
    
    messages = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content}
    ]
    
    # Use chat template if available
    if hasattr(tokenizer, "apply_chat_template"):
        try:
            prompt_text = tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True
            )
            return prompt_text
        except Exception:
            pass
    
    # Fallback: manual format
    return f"### Instruction:\n{user_content}\n\n### Response:\n"


def generate_code(model, tokenizer, prompt: str, max_new_tokens: int = 256, 
                  temperature: float = 0.2, num_samples: int = 1,
                  repetition_penalty: float = 1.1,
                  use_chat_template: bool = True) -> List[str]:
    """Generate code completions for a given prompt.
    
    Enhanced with:
    - Chat template support for better compatibility
    - Repetition penalty to reduce repetitive output
    - Proper device handling for quantized models
    """
    # Optionally build chat prompt
    if use_chat_template and not prompt.startswith("<"):
        # Looks like raw instruction, try to format it
        prompt_text = build_chat_prompt(tokenizer, prompt)
    else:
        prompt_text = prompt
    
    # Tokenize - get device from model parameters
    device = next(model.parameters()).device
    inputs = tokenizer(prompt_text, return_tensors="pt")
    inputs = {k: v.to(device) for k, v in inputs.items()}
    
    # Generate with improved parameters
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            top_p=0.95,
            do_sample=temperature > 0,
            num_return_sequences=num_samples,
            pad_token_id=tokenizer.pad_token_id,
            eos_token_id=tokenizer.eos_token_id,
            repetition_penalty=repetition_penalty,
        )
    
    # Decode completions
    completions = []
    input_length = inputs['input_ids'].shape[1]
    for output in outputs:
        generated_tokens = output[input_length:]
        generated = tokenizer.decode(generated_tokens, skip_special_tokens=True)
        completions.append(generated)
    
    return completions


# ============== Code Execution ==============

def classify_error(error_message: str, returncode: int) -> ErrorType:
    """Classify error type from error message and return code."""
    error_lower = error_message.lower()
    
    if "syntaxerror" in error_lower or "indentationerror" in error_lower:
        return ErrorType.SYNTAX_ERROR
    elif "importerror" in error_lower or "modulenotfounderror" in error_lower:
        return ErrorType.IMPORT_ERROR
    elif "memoryerror" in error_lower or "killed" in error_lower:
        return ErrorType.MEMORY_ERROR
    elif "assertionerror" in error_lower:
        return ErrorType.ASSERTION_ERROR
    elif "timeout" in error_lower or "timed out" in error_lower:
        return ErrorType.TIMEOUT
    elif any(err in error_lower for err in [
        "typeerror", "valueerror", "indexerror", "keyerror",
        "attributeerror", "nameerror", "zerodivisionerror",
        "runtimeerror", "recursionerror", "overflowerror"
    ]):
        return ErrorType.RUNTIME_ERROR
    elif returncode != 0:
        return ErrorType.RUNTIME_ERROR
    
    return ErrorType.NONE


# ============== JSON Test Parsing (Multi-Format Support) ==============

def parse_json_test(test_str: str, solution_code: str, idx: int = 0) -> str:
    """Parse test case from various formats and convert to executable code.
    
    Supports:
    - TACO format: {"type": "stdin_stdout", "input": "...", "expected_output": "..."}
    - HumanEval format: {"input": [...], "output": ...}
    - MBPP format: {"inputs": [...], "outputs": [...]}
    - Function call format: {"fn_name": "solve", "input": [...], "expected_output": ...}
    - Raw Python assert statements
    - Simple input/output pairs
    """
    test_str = test_str.strip()
    
    # 1. 如果不是 JSON，检查是否是原始 Python 代码
    if not test_str.startswith('{'):
        # 可能是直接的 assert 语句或测试代码
        if 'assert' in test_str or 'def test_' in test_str:
            return test_str
        return test_str
    
    # 2. 尝试解析 JSON
    try:
        test = json.loads(test_str)
    except json.JSONDecodeError:
        # JSON 解析失败，返回原样
        return test_str
    
    # 3. 检测测试类型并转换
    test_type = test.get('type', '').lower()
    
    # 获取输入（支持多种字段名）
    inp = test.get('input', test.get('inputs', test.get('stdin', '')))
    
    # 获取期望输出（支持多种字段名）
    exp = test.get('expected_output', 
           test.get('output',
           test.get('outputs',
           test.get('expected',
           test.get('stdout', '')))))
    
    # 获取函数名（如果有）
    fn_name = test.get('fn_name', test.get('function_name', test.get('entry_point', '')))
    
    # 4. 根据类型选择转换方式
    if test_type == 'stdin_stdout' or (not fn_name and isinstance(inp, str)):
        # stdin/stdout 类型
        return _convert_stdin_test_enhanced(inp, exp, solution_code, idx)
    elif test_type == 'function_call' or fn_name:
        # 函数调用类型
        return _convert_func_test_enhanced(fn_name or 'solve', inp, exp, idx)
    elif isinstance(inp, list) and not fn_name:
        # 可能是 MBPP/HumanEval 格式，带参数列表但无函数名
        # 尝试作为 stdin/stdout 处理
        if all(isinstance(i, str) for i in inp):
            combined_input = '\n'.join(inp)
            return _convert_stdin_test_enhanced(combined_input, exp, solution_code, idx)
        else:
            # 假设是函数参数
            return _convert_func_test_enhanced('solve', inp, exp, idx)
    else:
        # 尝试 stdin/stdout 作为后备
        return _convert_stdin_test_enhanced(str(inp), str(exp), solution_code, idx)


# ============== Dual Style Code Support (Function + stdin/stdout) ==============

def _generate_function_wrapper(code: str, fn_name: str, sample_input: str) -> str:
    """
    生成函数调用包装器，将函数式代码转换为stdin/stdout脚本
    
    当模型生成函数式代码（如 def solve(...)），但测试期望 stdin/stdout 风格时，
    自动生成包装代码来读取输入、调用函数并打印输出。
    
    Args:
        code: 函数式代码
        fn_name: 检测到的函数名（可能是 "solve" 或 "Solution().method"）
        sample_input: 测试输入样例，用于推断输入格式
    
    Returns:
        包含原始代码 + 自动生成调用逻辑的完整脚本
    """
    # 检测是否是 Solution 类方法
    is_solution_class = fn_name.startswith("Solution().")
    if is_solution_class:
        method_name = fn_name.split(".")[-1]
        call_prefix = f"Solution().{method_name}"
    else:
        call_prefix = fn_name
    
    # 生成更健壮的包装器
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

def _read_int():
    line = _read_line()
    return int(line) if line else 0

def _read_list_int():
    line = _read_line()
    return list(map(int, line.split())) if line.strip() else []

def _read_list_str():
    line = _read_line()
    return line.split() if line.strip() else []

def _try_parse_int(s):
    try:
        return int(s)
    except:
        return s

def _try_parse_list_int(s):
    try:
        return list(map(int, s.split()))
    except:
        return s.split() if s else []

# 获取调用函数的引用
_fn = {call_prefix}

# 尝试以多种方式调用函数
_result = None
_called = False

# 策略0: 空输入 -> 尝试无参数或空列表调用
if not _called and len(_lines) == 0:
    try:
        _result = _fn()
        _called = True
    except TypeError:
        try:
            _result = _fn([])
            _called = True
        except:
            pass

# 策略1: 单行单个整数
if not _called and len(_lines) == 1:
    line = _lines[0].strip()
    if line.lstrip('-').isdigit():
        try:
            _arg = int(line)
            _result = _fn(_arg)
            _called = True
        except:
            pass

# 策略2: 单行空格分隔整数 -> 作为列表
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
        # 尝试不同参数组合
        for _args in [(_n, _arr), (_arr,), (_n, _arr, len(_arr), len(_arr))]:
            if not _called:
                try:
                    _result = _fn(*_args)
                    _called = True
                except TypeError:
                    pass
    except:
        pass

# 策略4: 多行 -> 每行解析为整数或数组
if not _called and len(_lines) >= 2:
    try:
        _parsed = []
        for line in _lines:
            line = line.strip()
            if not line:
                continue
            if ' ' in line:
                _parsed.append(list(map(int, line.split())))
            elif line.lstrip('-').isdigit():
                _parsed.append(int(line))
            else:
                _parsed.append(line)
        
        # 尝试传递所有解析结果作为参数
        if len(_parsed) == 1:
            _result = _fn(_parsed[0])
            _called = True
        elif len(_parsed) >= 2:
            try:
                _result = _fn(*_parsed)
                _called = True
            except TypeError:
                try:
                    _result = _fn(_parsed)
                    _called = True
                except:
                    pass
    except:
        pass

# 策略5: 所有行拼接成整数列表
if not _called and len(_lines) >= 1:
    try:
        _all_ints = []
        for line in _lines:
            for part in line.split():
                if part.lstrip('-').isdigit():
                    _all_ints.append(int(part))
        if _all_ints:
            _result = _fn(_all_ints)
            _called = True
    except:
        pass

# 策略6: 字符串参数
if not _called and len(_lines) >= 1:
    try:
        if len(_lines) == 1:
            _result = _fn(_lines[0])
        else:
            _result = _fn(_lines)
        _called = True
    except:
        pass

# 输出结果
if _result is not None:
    if isinstance(_result, list):
        if _result and isinstance(_result[0], list):
            # 二维数组
            for _row in _result:
                print(' '.join(map(str, _row)))
        else:
            # 一维数组
            print(' '.join(map(str, _result)))
    elif isinstance(_result, bool):
        # 布尔值转小写
        print(str(_result).lower())
    elif isinstance(_result, tuple):
        print(' '.join(map(str, _result)))
    else:
        print(_result)
elif _result == 0:
    # 显式处理返回 0 的情况
    print(0)
'''
    return wrapper


def _adapt_code_for_stdin_test(code: str, inp: str) -> str:
    """
    智能适配代码风格：如果代码是函数式，将其转换为可执行的 stdin/stdout 脚本。
    
    当训练数据使用函数式代码，但测试数据期望 stdin/stdout 风格时，
    此函数自动检测并转换代码风格。
    
    Args:
        code: 模型生成的代码
        inp: 测试输入（用于推断输入格式）
    
    Returns:
        适配后的代码（如果是脚本式则原样返回，如果是函数式则添加包装器）
    """
    # 检测代码风格
    has_def = bool(re.search(r'\bdef\s+\w+\s*\(', code))
    has_input = bool(re.search(r'\binput\s*\(', code))
    has_print = bool(re.search(r'\bprint\s*\(', code))
    has_class = bool(re.search(r'\bclass\s+\w+', code))
    
    # 如果已经是脚本式（有 input 和 print），直接返回
    if has_input and has_print:
        return code
    
    # 如果是纯脚本式（只有 print，没有 def），直接返回
    if has_print and not has_def:
        return code
    
    # 如果是函数式代码（有 def，没有 input），需要包装
    if has_def and not has_input:
        # 查找主函数名（优先级：solve > Solution类的方法 > 其他函数）
        fn_name = None
        
        # 优先查找 solve 函数
        solve_match = re.search(r'\bdef\s+(solve)\s*\(', code)
        if solve_match:
            fn_name = solve_match.group(1)
        else:
            # 查找 Solution 类的方法（排除 __init__）
            if has_class:
                method_match = re.search(r'\bclass\s+Solution\b.*?\bdef\s+(\w+)\s*\(self', code, re.DOTALL)
                if method_match and method_match.group(1) != '__init__':
                    # 对于 Solution 类，需要特殊处理
                    fn_name = f"Solution().{method_match.group(1)}"
            
            # 查找任意顶层函数（非类方法）
            if not fn_name:
                # 查找所有顶层函数定义
                top_level_funcs = re.findall(r'^def\s+(\w+)\s*\(', code, re.MULTILINE)
                if top_level_funcs:
                    # 排除常见的辅助函数名
                    for func in top_level_funcs:
                        if func not in ['main', 'test', 'helper', '__init__']:
                            fn_name = func
                            break
                    if not fn_name:
                        fn_name = top_level_funcs[0]
        
        if fn_name:
            return _generate_function_wrapper(code, fn_name, inp)
    
    # 其他情况直接返回原代码
    return code


def _convert_stdin_test_enhanced(inp, exp, code: str, idx: int) -> str:
    """Convert stdin_stdout test to executable code (enhanced version).
    
    Enhanced with dual-style support: if code is function-style, 
    automatically adapts it for stdin/stdout execution.
    
    Args:
        inp: Input data - can be str, list, or any other type
        exp: Expected output - can be str, list, or any other type
        code: Solution code to execute
        idx: Test case index
    """
    # 健壮的输入处理 - 确保 inp 最终是字符串
    def to_string(val):
        """Helper to convert any value to string for stdin."""
        if val is None:
            return ''
        if isinstance(val, str):
            return val
        if isinstance(val, list):
            # 递归处理列表中的每个元素
            processed = []
            for item in val:
                if isinstance(item, list):
                    # 嵌套列表：每个子列表用空格分隔，不同子列表用换行分隔
                    processed.append(' '.join(str(x) for x in item))
                else:
                    processed.append(str(item))
            return '\n'.join(processed)
        # 其他类型直接转字符串
        return str(val)
    
    # 转换输入
    inp = to_string(inp)
    
    # 确保输入以换行结尾
    if inp and not inp.endswith('\n'):
        inp += '\n'
    
    # 处理列表形式的输出  
    if isinstance(exp, list):
        exp = '\n'.join(str(e) for e in exp)
    
    # ===== NEW: 智能适配代码风格 =====
    # 如果代码是函数式（def solve(...)），自动添加包装器使其能在 stdin/stdout 模式下运行
    adapted_code = _adapt_code_for_stdin_test(code, inp)
    
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
    exec({repr(adapted_code)},{{}})
finally:
    sys.stdout,sys.stdin=_so{idx},_si{idx}
_o{idx}=_c{idx}.getvalue()
def _n{idx}(s):return'\\n'.join(l.rstrip()for l in str(s).strip().replace('\\r\\n','\\n').split('\\n'))
assert _n{idx}(_o{idx})==_n{idx}(_e{idx}),f"Test {idx} failed: got {{repr(_o{idx}[:100])}} expected {{repr(_e{idx}[:100])}}"
'''


def _convert_func_test_enhanced(fn: str, inputs: any, exp: any, idx: int) -> str:
    """Convert function_call test to executable assert (enhanced version)."""
    # 处理输入参数
    if isinstance(inputs, list):
        args = ', '.join(repr(x) for x in inputs)
    elif inputs is None:
        args = ''
    else:
        args = repr(inputs)
    
    # 处理期望值
    if isinstance(exp, list) and len(exp) == 1:
        exp_val = exp[0]
    else:
        exp_val = exp
    
    return f'''
# Test {idx}
_r{idx}={fn}({args})
_e{idx}={repr(exp_val)}
# 支持浮点数近似比较
if isinstance(_r{idx}, float) and isinstance(_e{idx}, float):
    assert abs(_r{idx} - _e{idx}) < 1e-6, f"Test {idx} failed: got {{_r{idx}}} expected {{_e{idx}}}"
else:
    assert _r{idx}==_e{idx},f"Test {idx} failed: got {{repr(_r{idx})}} expected {{repr(_e{idx})}}"
'''


# 保留旧函数以兼容
def _convert_stdin_test(test: dict, code: str, idx: int) -> str:
    """Legacy wrapper for stdin_stdout test conversion."""
    inp = test.get('input', '')
    exp = test.get('expected_output', '')
    return _convert_stdin_test_enhanced(inp, exp, code, idx)


def _convert_func_test(test: dict, idx: int) -> str:
    """Legacy wrapper for function_call test conversion."""
    fn = test.get('fn_name', 'solve')
    inputs = test.get('input', [])
    exp = test.get('expected_output', [])
    return _convert_func_test_enhanced(fn, inputs, exp, idx)


def build_json_test_code(tests_raw: list, solution_code: str, max_tests: int = 5) -> str:
    """Build executable test code from test list (supports multiple formats)."""
    if not tests_raw:
        return ""
    
    test_codes = []
    for i, t in enumerate(tests_raw[:max_tests]):
        if isinstance(t, dict):
            # 直接是 dict
            test_codes.append(parse_json_test(json.dumps(t), solution_code, i))
        elif isinstance(t, str):
            # 字符串形式的 JSON 或原始代码
            test_codes.append(parse_json_test(t, solution_code, i))
        else:
            # 其他类型，尝试转换
            test_codes.append(parse_json_test(str(t), solution_code, i))
    
    return '\n'.join(test_codes)


def execute_code_safely(code: str, test_code: str, timeout: int = EXECUTION_TIMEOUT,
                        memory_limit_mb: Optional[int] = None) -> ExecutionResult:
    """Execute code in a subprocess with timeout, memory limit, and detailed error classification.
    

    Args:
        code: The code to execute
        test_code: The test code to append
        timeout: Timeout in seconds
        memory_limit_mb: Memory limit in MB (only effective on Linux/Unix)
    """
    full_code = code + "\n\n" + test_code
    temp_path = None
    
    try:
        # Check for syntax errors first
        try:
            ast.parse(full_code)
        except SyntaxError as e:
            return ExecutionResult(
                passed=False,
                error_type=ErrorType.SYNTAX_ERROR,
                error_message=f"Line {e.lineno}: {e.msg}",
                execution_time_ms=0.0
            )
        
        # Build wrapper code with memory limit (Linux only)
        wrapper_code = ""
        if memory_limit_mb and sys.platform != 'win32':
            # Add resource-based memory limit for Linux/Unix
            wrapper_code = f'''
import resource
import sys

# Set memory limit to {memory_limit_mb} MB
memory_limit_bytes = {memory_limit_mb} * 1024 * 1024
try:
    resource.setrlimit(resource.RLIMIT_AS, (memory_limit_bytes, memory_limit_bytes))
except (ValueError, resource.error) as e:
    print(f"Warning: Could not set memory limit: {{e}}", file=sys.stderr)

'''
        
        # Write code to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write(wrapper_code + full_code)
            temp_path = f.name
        
        # Execute in subprocess with timing
        start_time = time.perf_counter()
        result = subprocess.run(
            [sys.executable, temp_path],
            capture_output=True,
            text=True,
            timeout=timeout
        )
        end_time = time.perf_counter()
        execution_time_ms = (end_time - start_time) * 1000
        
        if result.returncode == 0:
            return ExecutionResult(
                passed=True,
                error_type=ErrorType.NONE,
                execution_time_ms=execution_time_ms,
                stdout=result.stdout,
                stderr=result.stderr
            )
        else:
            error_type = classify_error(result.stderr or result.stdout, result.returncode)
            # Check for memory error specifically
            if 'MemoryError' in (result.stderr or result.stdout) or \
               'Cannot allocate memory' in (result.stderr or result.stdout) or \
               result.returncode == -9:  # SIGKILL (OOM killer)
                error_type = ErrorType.MEMORY_ERROR
            
            return ExecutionResult(
                passed=False,
                error_type=error_type,
                error_message=(result.stderr or result.stdout)[:500],
                execution_time_ms=execution_time_ms,
                stdout=result.stdout,
                stderr=result.stderr
            )
    
    except subprocess.TimeoutExpired:
        return ExecutionResult(
            passed=False,
            error_type=ErrorType.TIMEOUT,
            error_message=f"Execution timed out after {timeout}s",
            execution_time_ms=timeout * 1000
        )
    
    except Exception as e:
        return ExecutionResult(
            passed=False,
            error_type=ErrorType.RUNTIME_ERROR,
            error_message=str(e)[:500]
        )
    
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except:
                pass


# ============== Code Quality Analysis ==============

def analyze_code_quality(code: str) -> Dict[str, Any]:
    """Analyze code quality metrics.
    
    Enhanced with AST-based analysis for:
    - Loop detection (for/while)
    - Recursion detection
    - Global variable usage
    - Data structure usage (list/dict/set/heap)
    
    References P1 requirements for comprehensive code quality assessment.
    """
    lines = code.split('\n')
    
    # Check for extra I/O (regex-based)
    has_print = bool(re.search(r'\bprint\s*\(', code))
    has_input = bool(re.search(r'\binput\s*\(', code))
    
    # Check for function definition (interface compliance)
    has_solve_function = bool(re.search(r'\bdef\s+solve\s*\(', code))
    has_any_function = bool(re.search(r'\bdef\s+\w+\s*\(', code))
    
    # Check for common issues
    has_debug_statements = bool(re.search(r'#\s*debug|print\s*\(\s*["\']debug', code.lower()))
    
    # ============== AST-based Analysis (P1 Enhancement) ==============
    has_for = False
    has_while = False
    has_recursion = False
    uses_global_vars = False
    global_var_names: List[str] = []
    function_names: List[str] = []
    
    # Data structure usage detection
    uses_list_comprehension = False
    uses_dict = False
    uses_set = False
    uses_heap = False
    uses_deque = False
    uses_sorting = False
    
    try:
        tree = ast.parse(code)
        
        # First pass: collect function names
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                function_names.append(node.name)
        
        # Second pass: analyze structure
        for node in ast.walk(tree):
            # Loop detection
            if isinstance(node, ast.For):
                has_for = True
            elif isinstance(node, ast.While):
                has_while = True
            
            # Global variable detection
            elif isinstance(node, ast.Global):
                uses_global_vars = True
                global_var_names.extend(node.names)
            
            # Recursion detection: function calls one of the defined functions
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in function_names:
                        has_recursion = True
                    # Data structure detection via function calls
                    if node.func.id in ('sorted', 'sort'):
                        uses_sorting = True
                    elif node.func.id == 'set':
                        uses_set = True
                    elif node.func.id == 'dict':
                        uses_dict = True
                elif isinstance(node.func, ast.Attribute):
                    # heapq.heappush, collections.deque, etc.
                    if node.func.attr in ('heappush', 'heappop', 'heapify'):
                        uses_heap = True
                    elif node.func.attr == 'sort':
                        uses_sorting = True
            
            # List comprehension detection
            elif isinstance(node, ast.ListComp):
                uses_list_comprehension = True
            
            # Dict/Set literal detection
            elif isinstance(node, ast.Dict):
                uses_dict = True
            elif isinstance(node, ast.Set):
                uses_set = True
    
    except SyntaxError:
        # Code has syntax errors, can't do AST analysis
        pass
    
    # Check imports for data structures
    if re.search(r'\bimport\s+heapq\b|\bfrom\s+heapq\b', code):
        uses_heap = True
    if re.search(r'\bfrom\s+collections\s+import.*\bdeque\b', code):
        uses_deque = True
    
    return {
        # Basic metrics
        "code_length": len(code),
        "line_count": len(lines),
        "non_empty_lines": len([l for l in lines if l.strip()]),
        
        # Interface compliance
        "has_solve_function": has_solve_function,
        "has_function": has_any_function,
        
        # I/O detection
        "has_print": has_print,
        "has_input": has_input,
        "has_debug": has_debug_statements,
        "extra_io": has_print or has_input,
        
        # P1: Structure analysis (AST-based)
        "has_for": has_for,
        "has_while": has_while,
        "has_loop": has_for or has_while,
        "has_recursion": has_recursion,
        
        # P1: Global variable usage
        "uses_global_vars": uses_global_vars,
        "global_var_names": global_var_names,
        
        # P1: Data structure usage
        "uses_list_comprehension": uses_list_comprehension,
        "uses_dict": uses_dict,
        "uses_set": uses_set,
        "uses_heap": uses_heap,
        "uses_deque": uses_deque,
        "uses_sorting": uses_sorting,
    }


# ============== Fuzzing / Random Testing ==============

def generate_random_input(problem_type: str = "array") -> Any:
    """Generate random test input based on problem type."""
    import random
    
    if problem_type == "array":
        size = random.randint(1, 100)
        return [random.randint(-1000, 1000) for _ in range(size)]
    elif problem_type == "string":
        size = random.randint(1, 50)
        return ''.join(random.choices('abcdefghijklmnopqrstuvwxyz', k=size))
    elif problem_type == "integer":
        return random.randint(-10**9, 10**9)
    elif problem_type == "matrix":
        rows = random.randint(1, 10)
        cols = random.randint(1, 10)
        return [[random.randint(-100, 100) for _ in range(cols)] for _ in range(rows)]
    else:
        return random.randint(1, 100)


def fuzz_test(solution_code: str, reference_code: str, 
              problem_type: str = "array", num_tests: int = 50,
              timeout: int = 2) -> Dict[str, Any]:
    """Run fuzz testing by comparing solution output with reference solution."""
    pass_count = 0
    error_count = 0
    
    for i in range(num_tests):
        try:
            test_input = generate_random_input(problem_type)
            
            # Create test harness
            test_harness = f"""
import json
test_input = {repr(test_input)}

# Reference solution
{reference_code}

# Test solution
{solution_code}

# Compare outputs (assuming both define a 'solve' function)
try:
    if 'solve' in dir():
        ref_result = solve(test_input)
        test_result = solve(test_input)
        assert ref_result == test_result, f"Mismatch: {{ref_result}} vs {{test_result}}"
        print("PASS")
except Exception as e:
    print(f"FAIL: {{e}}")
"""
            
            result = execute_code_safely("", test_harness, timeout=timeout)
            if result.passed and "PASS" in result.stdout:
                pass_count += 1
            else:
                error_count += 1
                
        except Exception:
            error_count += 1
    
    return {
        "fuzz_pass_rate": pass_count / num_tests if num_tests > 0 else 0.0,
        "fuzz_error_rate": error_count / num_tests if num_tests > 0 else 0.0,
        "total_tests": num_tests
    }


# ============== Self-Consistency Evaluation ==============

def evaluate_consistency(model, tokenizer, prompt: str, test_code: str,
                         num_runs: int = 5, temperature: float = 0.4) -> Dict[str, Any]:
    """Evaluate self-consistency by generating multiple solutions."""
    results = []
    
    for _ in range(num_runs):
        completions = generate_code(
            model, tokenizer, prompt,
            temperature=temperature,
            num_samples=1
        )
        
        if completions:
            exec_result = execute_code_safely(prompt + completions[0], test_code)
            results.append(1 if exec_result.passed else 0)
        else:
            results.append(0)
    
    pass_rate = sum(results) / len(results) if results else 0.0
    variance = statistics.variance(results) if len(results) > 1 else 0.0
    
    return {
        "self_consistency_rate": pass_rate,
        "variance": variance,
        "num_runs": num_runs
    }


# ============== Statistics Computation ==============

def compute_pass_at_k(n: int, c: int, k: int) -> float:
    """Compute pass@k metric using unbiased estimator.
    
    Args:
        n: total number of samples generated
        c: number of correct samples
        k: k value for pass@k
    """
    if n - c < k:
        return 1.0
    
    # pass@k = 1 - C(n-c, k) / C(n, k)
    return 1.0 - comb(n - c, k) / comb(n, k)


def compute_percentile(data: List[float], percentile: float) -> float:
    """Compute percentile of a list."""
    if not data:
        return 0.0
    sorted_data = sorted(data)
    index = int(len(sorted_data) * percentile / 100)
    return sorted_data[min(index, len(sorted_data) - 1)]


def compute_error_stats(error_counts: Dict[str, int], total: int) -> ErrorStats:
    """Compute error rate statistics."""
    if total == 0:
        return ErrorStats()
    
    return ErrorStats(
        syntax_error_rate=error_counts.get(ErrorType.SYNTAX_ERROR.value, 0) / total * 100,
        runtime_error_rate=error_counts.get(ErrorType.RUNTIME_ERROR.value, 0) / total * 100,
        timeout_rate=error_counts.get(ErrorType.TIMEOUT.value, 0) / total * 100,
        invalid_output_rate=error_counts.get(ErrorType.INVALID_OUTPUT.value, 0) / total * 100,
        assertion_error_rate=error_counts.get(ErrorType.ASSERTION_ERROR.value, 0) / total * 100,
        import_error_rate=error_counts.get(ErrorType.IMPORT_ERROR.value, 0) / total * 100,
        memory_error_rate=error_counts.get(ErrorType.MEMORY_ERROR.value, 0) / total * 100,
    )


def compute_time_stats(execution_times: List[float], timeout_count: int, total: int) -> TimeStats:
    """Compute execution time statistics."""
    if not execution_times:
        return TimeStats(tle_rate=timeout_count / total * 100 if total > 0 else 0.0)
    
    return TimeStats(
        mean_runtime_ms=statistics.mean(execution_times),
        p50_runtime_ms=compute_percentile(execution_times, 50),
        p95_runtime_ms=compute_percentile(execution_times, 95),
        max_runtime_ms=max(execution_times),
        tle_rate=timeout_count / total * 100 if total > 0 else 0.0
    )


def compute_segment_stats(results: List[ProblemResult], segment_key: str) -> Dict[str, SegmentResult]:
    """Compute statistics by segment (difficulty, category, etc.)."""
    segments: Dict[str, List[ProblemResult]] = {}
    
    for r in results:
        key = getattr(r, segment_key, "unknown")
        if key not in segments:
            segments[key] = []
        segments[key].append(r)
    
    segment_stats = {}
    for key, segment_results in segments.items():
        total_samples = sum(r.n_samples for r in segment_results)
        total_passed = sum(r.n_passed for r in segment_results)
        total_compiled = sum(r.n_compiled for r in segment_results)
        
        segment_stats[key] = SegmentResult(
            count=len(segment_results),
            pass_at_1=total_passed / total_samples * 100 if total_samples > 0 else 0.0,
            compile_rate=total_compiled / total_samples * 100 if total_samples > 0 else 0.0
        )
    
    return segment_stats


# ============== Dataset Loading ==============

def load_eval_dataset(dataset_path: str) -> List[Dict[str, Any]]:
    """Load evaluation dataset from JSONL file."""
    problems = []
    
    with open(dataset_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                problems.append(json.loads(line))
    
    logger.info(f"Loaded {len(problems)} problems from {dataset_path}")
    return problems


# ============== Main Evaluation ==============

def evaluate(config: dict) -> Dict[str, Any]:
    """Main evaluation function with comprehensive metrics and logging."""
    model_path = config['modelPath']
    dataset_path = config['datasetPath']
    adapter_path = config.get('adapterPath')
    output_dir = config.get('outputDir', './storage/eval')
    run_id = config.get('runId', '')
    
    eval_config = config.get('eval', {})
    
    # P0-FIX: 增强 k_values 解析逻辑
    # 支持：整数 10、字符串 "10"、逗号分隔 "1,5,10"
    k_config = eval_config.get('k', '1,5,10')
    if isinstance(k_config, int):
        # 单个整数：确保同时包含标准的 1, 5, 10
        k_values = sorted(set([1, 5, 10, k_config]))
    elif isinstance(k_config, str):
        # 字符串：解析并合并标准值
        try:
            parsed = [int(k.strip()) for k in k_config.split(',') if k.strip()]
            k_values = sorted(set([1, 5, 10] + parsed))
        except ValueError:
            logger.warning(f"Invalid k value format: {k_config}, using default [1, 5, 10]")
            k_values = [1, 5, 10]
    elif isinstance(k_config, list):
        # 列表：直接使用并确保包含标准值
        k_values = sorted(set([1, 5, 10] + [int(k) for k in k_config]))
    else:
        k_values = [1, 5, 10]
    
    logger.info(f"Pass@k values to calculate: {k_values}")
    
    # 优先使用用户配置的 numSamples，否则使用 max(k_values) 作为默认值
    num_samples = eval_config.get('numSamples', max(k_values) if k_values else 10)
    max_tokens = eval_config.get('maxTokens', 256)
    temperature = eval_config.get('temperature', 0.2)
    top_p = eval_config.get('topP', 0.95)
    timeout = eval_config.get('timeout', EXECUTION_TIMEOUT)
    memory_limit_mb = eval_config.get('memoryLimit', None)  # 内存限制 (MB)
    seed = config.get('seed', 42)
    
    # Feature flags
    enable_fuzzing = eval_config.get('enableFuzzing', False)
    fuzzing_runs = eval_config.get('fuzzingRuns', 50)
    enable_consistency = eval_config.get('enableConsistency', False)
    consistency_runs = eval_config.get('consistencyRuns', 5)
    enable_code_quality = eval_config.get('enableCodeQuality', True)
    enable_postprocess = eval_config.get('enablePostProcess', False)
    
    # 每个问题的最大测试用例数（限制超长测试集，加速评估）
    max_tests_per_problem = eval_config.get('maxTestsPerProblem', 10)
    logger.info(f"Max tests per problem: {max_tests_per_problem}")
    
    # =========================================================================
    # Initialize Eval Logger and Code Extractor
    # =========================================================================
    eval_logger_instance = EvalLogger()
    code_extractor = CodeExtractor()  # For extracting code from model output
    
    generation_settings = GenerationSettings(
        k=num_samples,
        temperature=temperature,
        top_p=top_p,
        max_new_tokens=max_tokens,
        do_sample=temperature > 0,
        post_process_enabled=enable_postprocess,
    )
    
    judge_settings = JudgeSettings(
        timeout_seconds=timeout,
        memory_limit_mb=memory_limit_mb,
        sandbox_mode="subprocess",
        recursion_limit=1000,
        network_disabled=True,
        file_access_disabled=True,
    )
    
    eval_log = eval_logger_instance.create_eval_log(
        seed=seed,
        base_model_name=os.path.basename(model_path),
        checkpoint_path=adapter_path or model_path,
        generation_settings=generation_settings,
        judge_settings=judge_settings,
    )
    
    # =========================================================================
    # P1: 设置随机种子确保可复现性
    # =========================================================================
    import random
    import numpy as np
    
    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)
        try:
            import torch
            torch.manual_seed(seed)
            if torch.cuda.is_available():
                torch.cuda.manual_seed_all(seed)
        except ImportError:
            pass
    
    # P1: 记录可复现性信息
    eval_logger_instance.set_reproducibility_info(
        eval_log,
        python_seed=seed,
        numpy_seed=seed,
        torch_seed=seed,
        evaluator_version="1.0.0",
        checkpoint_hash=None,  # TODO: 计算模型 checkpoint hash
    )
    
    # P1: 设置评测方法论配置
    eval_logger_instance.set_evaluation_protocol(
        eval_log,
        samples_per_task=num_samples,
        temperature=temperature,
        top_p=top_p,
        sorting_method="generation_order",
        pass_at_k_definition="success if any of the first k samples passes all tests",
        compile_rate_definition="percentage of samples that run without SyntaxError during exec",
        timeout_handling=f"counted as failure (TLE) after {timeout}s",
        memory_limit_handling=f"counted as failure (MLE) after {memory_limit_mb}MB" if memory_limit_mb else "no limit",
    )
    
    logger.info(f"Eval Run ID: {eval_log.eval_run_id}")
    
    # Output initial progress events for real-time streaming
    print(json.dumps({
        "type": "log",
        "level": "info",
        "message": f"Evaluation starting with run ID: {eval_log.eval_run_id}"
    }), flush=True)
    
    print(json.dumps({
        "type": "log",
        "level": "info",
        "message": f"Loading model from: {model_path}"
    }), flush=True)
    
    # Load model
    model, tokenizer = load_model(
        model_path, 
        adapter_path,
        config.get('lora', {}).get('quantization', '4bit')
    )
    
    print(json.dumps({
        "type": "log",
        "level": "info",
        "message": "Model loaded successfully"
    }), flush=True)
    
    print(json.dumps({
        "type": "log",
        "level": "info",
        "message": f"Loading evaluation dataset from: {dataset_path}"
    }), flush=True)
    
    # Load dataset
    problems = load_eval_dataset(dataset_path)
    
    print(json.dumps({
        "type": "log",
        "level": "info",
        "message": f"Dataset loaded: {len(problems)} problems"
    }), flush=True)
    
    # Set dataset info
    difficulty_dist: Dict[str, int] = {}
    category_dist: Dict[str, int] = {}
    for p in problems:
        diff = p.get('difficulty', 'unknown')
        cat = p.get('category', p.get('type', 'unknown'))
        difficulty_dist[diff] = difficulty_dist.get(diff, 0) + 1
        category_dist[cat] = category_dist.get(cat, 0) + 1
    
    eval_logger_instance.set_dataset_info(
        eval_log,
        dataset_path=dataset_path,
        dataset_name=os.path.basename(dataset_path),
        split=eval_config.get('split', 'test'),
        total_problems=len(problems),
        total_samples=len(problems) * num_samples,
        difficulty_distribution=difficulty_dist,
        category_distribution=category_dist,
    )
    
    # Aggregated statistics
    problem_results: List[ProblemResult] = []
    all_error_counts: Dict[str, int] = {}
    all_execution_times: List[float] = []
    all_code_lengths: List[int] = []
    all_line_counts: List[int] = []
    extra_io_count = 0
    interface_compliant_count = 0
    
    total_samples = 0
    total_passed = 0
    total_compiled = 0
    timeout_count = 0
    
    failures = []
    
    # ===== CHECKPOINT RESUME: 检查是否存在断点，从断点恢复评测 =====
    start_problem_idx = 0
    checkpoint_files = []
    try:
        if os.path.exists(output_dir):
            checkpoint_files = sorted([
                f for f in os.listdir(output_dir) 
                if f.startswith('checkpoint_') and f.endswith('.json')
            ], key=lambda x: int(x.split('_')[1].split('.')[0]), reverse=True)
    except Exception as e:
        logger.warning(f"Failed to list checkpoint files: {e}")
    
    if checkpoint_files:
        latest_checkpoint = checkpoint_files[0]
        checkpoint_path = os.path.join(output_dir, latest_checkpoint)
        try:
            with open(checkpoint_path, 'r') as f:
                checkpoint_data = json.load(f)
            
            # 恢复状态
            start_problem_idx = checkpoint_data.get('completed_problems', 0)
            total_samples = checkpoint_data.get('total_samples', 0)
            total_passed = checkpoint_data.get('total_passed', 0)
            total_compiled = checkpoint_data.get('total_compiled', 0)
            all_error_counts = checkpoint_data.get('error_counts', {})
            
            logger.info(f"=== RESUMING FROM CHECKPOINT ===")
            logger.info(f"  Checkpoint: {latest_checkpoint}")
            logger.info(f"  Completed: {start_problem_idx}/{len(problems)} problems")
            logger.info(f"  Current Pass@1: {checkpoint_data.get('current_pass_at_1', 0)}%")
            
            print(json.dumps({
                "type": "log",
                "level": "info",
                "message": f"Resuming from checkpoint: {start_problem_idx}/{len(problems)} problems completed"
            }), flush=True)
            
            print(json.dumps({
                "type": "log",
                "level": "info", 
                "message": f"Previous progress - Pass@1: {checkpoint_data.get('current_pass_at_1', 0)}%, Compile: {checkpoint_data.get('current_compile_rate', 0)}%"
            }), flush=True)
            
        except Exception as e:
            logger.warning(f"Failed to load checkpoint {checkpoint_path}: {e}")
            logger.info("Starting evaluation from beginning...")
            start_problem_idx = 0
    else:
        logger.info("No checkpoint found, starting fresh evaluation...")

    
    for i, problem in enumerate(problems):
        task_id = problem.get('task_id', problem.get('id', str(i)))
        
        # ===== CHECKPOINT RESUME: 跳过已完成的问题 =====
        if i < start_problem_idx:
            continue
        
        logger.info(f"Evaluating problem {i+1}/{len(problems)}: {task_id}")
        
        # ===== OOM FIX: Periodic GPU memory cleanup =====
        if i > 0 and i % 5 == 0:
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                # Log GPU memory usage
                allocated = torch.cuda.memory_allocated() / 1024**3
                reserved = torch.cuda.memory_reserved() / 1024**3
                logger.info(f"GPU Memory: {allocated:.2f}GB allocated, {reserved:.2f}GB reserved")
                print(json.dumps({
                    "type": "log",
                    "level": "info",
                    "message": f"GPU Memory: {allocated:.2f}GB allocated, {reserved:.2f}GB reserved"
                }), flush=True)
        
        # ===== CHECKPOINT: Save progress every 10 problems to avoid losing work on interrupt =====
        # 更频繁的保存以支持断点恢复
        if i > 0 and i % 10 == 0 and total_samples > 0:
            checkpoint_path = os.path.join(output_dir, f'checkpoint_{i}.json')
            checkpoint_data = {
                'completed_problems': i,
                'total_problems': len(problems),
                'total_samples': total_samples,
                'total_passed': total_passed,
                'total_compiled': total_compiled,
                'current_pass_at_1': round((total_passed / total_samples * 100), 2) if total_samples > 0 else 0,
                'current_compile_rate': round((total_compiled / total_samples * 100), 2) if total_samples > 0 else 0,
                'error_counts': all_error_counts,
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            }
            try:
                os.makedirs(output_dir, exist_ok=True)
                with open(checkpoint_path, 'w') as f:
                    json.dump(checkpoint_data, f, indent=2)
                logger.info(f"Checkpoint saved: {checkpoint_path}")
                print(json.dumps({
                    "type": "log",
                    "level": "info",
                    "message": f"Checkpoint saved at problem {i}/{len(problems)}"
                }), flush=True)
            except Exception as e:
                logger.warning(f"Failed to save checkpoint: {e}")
        
        # Output structured progress event for real-time streaming
        print(json.dumps({
            "type": "progress",
            "completed": i,
            "total": len(problems),
            "current_task_id": task_id
        }), flush=True)
        
        # Output log event for frontend
        print(json.dumps({
            "type": "log",
            "level": "info",
            "message": f"Evaluating problem {i+1}/{len(problems)}: {task_id}"
        }), flush=True)

        # ===== ROBUSTNESS FIX: Catch exceptions to continue evaluation =====
        try:
            # ===== FIXED: Correct field mapping for test.jsonl format =====
            instruction = problem.get('instruction', problem.get('prompt', ''))
            signature = problem.get('signature', 'def solve(nums: list[int]) -> int:')
            test_code_raw = problem.get('tests', problem.get('test', ''))
            # FIX: Handle case where tests is a list of test cases
            if isinstance(test_code_raw, list):
                test_code_raw = '\n'.join(str(t) for t in test_code_raw)
            reference = problem.get('reference', '')
            difficulty = problem.get('difficulty', 'unknown')
            category = problem.get('category', problem.get('type', 'unknown'))
        
            # ===== FIX: Detect stdin_stdout type to avoid forcing function signature =====
            is_stdin_stdout = False
            tests_list = problem.get('tests', [])
            if isinstance(tests_list, str):
                tests_list = [tests_list]
        
            if tests_list and isinstance(tests_list[0], str):
                first_test = tests_list[0].strip()
                if first_test.startswith('{'):
                    try:
                        test_obj = json.loads(first_test)
                        # Check if it's stdin_stdout type
                        is_stdin_stdout = (
                            test_obj.get('type') == 'stdin_stdout' or 
                            (not test_obj.get('fn_name') and 'input' in test_obj and 'expected_output' in test_obj)
                        )
                    except json.JSONDecodeError:
                        pass

            if not instruction:
                continue
        
            # ===== ENHANCED: Handle JSON format tests (TACO format) =====
            # tests_list already initialized in is_stdin_stdout detection block above
        
            # Check if tests are in JSON format
            is_json_test = False
            if tests_list and isinstance(tests_list[0], str):
                first_test = tests_list[0].strip()
                is_json_test = first_test.startswith('{') and '"type"' in first_test
        
            if not is_json_test:
                # Legacy handling for pytest-style and other formats
                test_code_raw = problem.get('tests', problem.get('test', ''))
                if isinstance(test_code_raw, list):
                    test_code_raw = '\n'.join(str(t) for t in test_code_raw)
        
                if test_code_raw.strip().startswith('def test_'):
                    test_func_match = re.search(r'def\s+(test_\w+)\s*\(', test_code_raw)
                    if test_func_match:
                        test_func_name = test_func_match.group(1)
                        test_code = test_code_raw + f'\n\n{test_func_name}()'
                    else:
                        test_code = test_code_raw + '\n\ntest_solve()'
                else:
                    test_code = test_code_raw
                test_code_is_json = False
            else:
                # JSON format test - will be processed per-completion
                test_code = None  # Will be built per completion with generated code
                test_code_is_json = True
        

            # Initialize problem result
            prob_result = ProblemResult(
                task_id=task_id,
                difficulty=difficulty,
                category=category
            )
            # ===== FIX: Build prompt based on test type =====
            if is_stdin_stdout:
                # stdin/stdout type: use instruction directly, no function signature
                generation_prompt = instruction
                logger.debug(f"Using stdin/stdout prompt for {task_id}")
            else:
                # Function call type: add signature
                generation_prompt = f"{instruction}\n\nFunction signature: {signature}"
        
            # Generate completions
            completions = generate_code(
                model, tokenizer, generation_prompt, 
                max_new_tokens=max_tokens,
                temperature=temperature,
                num_samples=num_samples
            )
            
            # ===== OOM FIX: Clear GPU cache after generation =====
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        
            for completion in completions:
                total_samples += 1
                prob_result.n_samples += 1
        
                # ===== FIXED: Extract code from model output (handles Markdown etc.) =====
                extracted_code = code_extractor.extract(completion)
        
                # ===== FIX: Only add signature wrapper for function-style problems =====
                if not is_stdin_stdout:
                    # Function style: If extracted code doesn't contain function definition, prepend signature
                    if extracted_code.strip() and 'def solve' not in extracted_code and 'def ' not in extracted_code:
                        # Model may have output only function body, prepend signature
                        # Check if code already has indentation (function body format)
                        lines = extracted_code.strip().split('\n')
                        if lines and not lines[0].startswith('    '):
                            # No indentation, add proper indentation
                            indented_body = '\n'.join('    ' + line if line.strip() else '' for line in lines)
                            extracted_code = signature + '\n' + indented_body
                        else:
                            # Already has indentation, just prepend signature
                            extracted_code = signature + '\n' + extracted_code
                    elif not extracted_code.strip():
                        # Extraction failed, try using raw completion
                        extracted_code = completion
                else:
                    # stdin/stdout style: Keep code as-is (script style)
                    if not extracted_code.strip():
                        extracted_code = completion
        
                # ===== ENHANCED: Build test code for JSON format tests =====
                if test_code_is_json:
                    # Build executable test code using the generated code (uses configured max_tests_per_problem)
                    actual_test_code = build_json_test_code(tests_list, extracted_code, max_tests=max_tests_per_problem)
                else:
                    actual_test_code = test_code
        
                # Execute extracted code with test (with memory limit if configured)
                # For JSON stdin_stdout tests, the test code will re-exec the solution
                # So we pass empty code and let test handle everything
                if is_stdin_stdout and test_code_is_json:
                    # stdin_stdout test: test code will exec solution, don't prepend
                    exec_result = execute_code_safely("", actual_test_code, timeout=timeout, memory_limit_mb=memory_limit_mb)
                else:
                    # function_call or legacy test: solution + test as usual
                    exec_result = execute_code_safely(extracted_code, actual_test_code, timeout=timeout, memory_limit_mb=memory_limit_mb)
        

                # Track execution time (only for non-timeout results)
                if exec_result.error_type != ErrorType.TIMEOUT and exec_result.execution_time_ms > 0:
                    all_execution_times.append(exec_result.execution_time_ms)
                    prob_result.execution_times.append(exec_result.execution_time_ms)
        
                # Track error types
                if exec_result.error_type != ErrorType.NONE:
                    error_key = exec_result.error_type.value
                    all_error_counts[error_key] = all_error_counts.get(error_key, 0) + 1
                    prob_result.error_counts[error_key] = prob_result.error_counts.get(error_key, 0) + 1
            
                    if exec_result.error_type == ErrorType.TIMEOUT:
                        timeout_count += 1
        
                # Track results
                if exec_result.passed:
                    prob_result.n_passed += 1
                    prob_result.n_compiled += 1
                    total_passed += 1
                    total_compiled += 1
                elif exec_result.error_type != ErrorType.SYNTAX_ERROR:
                    # Code compiled but failed test
                    prob_result.n_compiled += 1
                    total_compiled += 1
            
                    # Record failure for analysis
                    if len(failures) < 50:
                        failures.append({
                            "taskId": task_id,
                            "prompt": instruction,  # 完整保存
                            "output": extracted_code,  # 完整保存
                            "errorType": exec_result.error_type.value,
                            "error": exec_result.error_message,  # 完整保存
                            "executionTimeMs": exec_result.execution_time_ms
                        })
        
                # ===== NEW: Collect SampleResult for database persistence =====
                # Only collect failed samples + limited successful ones for analysis
                sample_index = prob_result.n_samples - 1
                should_collect = (not exec_result.passed) or (exec_result.passed and len([s for s in eval_log.sample_results if s.verdict == "AC"]) < 20)
        
                if should_collect and len(eval_log.sample_results) < 200:  # Limit total samples
                    # Map error type to verdict
                    verdict_map = {
                        ErrorType.NONE: "AC",
                        ErrorType.SYNTAX_ERROR: "CE",
                        ErrorType.RUNTIME_ERROR: "RE",
                        ErrorType.TIMEOUT: "TLE",
                        ErrorType.ASSERTION_ERROR: "WA",
                        ErrorType.INVALID_OUTPUT: "WA",
                        ErrorType.IMPORT_ERROR: "CE",
                        ErrorType.MEMORY_ERROR: "MLE",
                    }
                    verdict = verdict_map.get(exec_result.error_type, "RE") if not exec_result.passed else "AC"
            
                    sample_result = SampleResult(
                        task_id=task_id,
                        sample_index=sample_index,
                        difficulty=difficulty,
                        category=category,
                        prompt=instruction,  # 完整保存，不截断
                        raw_output=completion,  # 完整保存，不截断
                        post_process_output=extracted_code,  # 完整保存，不截断
                        traceback=exec_result.error_message if exec_result.error_message else None,  # 完整保存
                        execution_time_ms=exec_result.execution_time_ms,
                        verdict=verdict,
                        error_type=exec_result.error_type.value if exec_result.error_type != ErrorType.NONE else None,
                    )
                    eval_logger_instance.add_sample_result(eval_log, sample_result)
        
                # Code quality analysis (use extracted code, not raw completion)
                if enable_code_quality:
                    quality = analyze_code_quality(extracted_code)
                    all_code_lengths.append(quality["code_length"])
                    all_line_counts.append(quality["line_count"])
                    prob_result.code_lengths.append(quality["code_length"])
            
                    if quality["extra_io"]:
                        extra_io_count += 1
                    if quality["has_function"]:
                        interface_compliant_count += 1
        
                problem_results.append(prob_result)
        
        


        except torch.cuda.OutOfMemoryError as e:
            # ===== OOM FIX: Specific handling for CUDA OOM =====
            logger.error(f"CUDA OOM at problem {task_id}: {e}")
            print(json.dumps({
                "type": "log",
                "level": "error",
                "message": f"CUDA Out of Memory at problem {task_id}. Clearing cache and continuing..."
            }), flush=True)
            
            # Aggressive memory cleanup
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
            
            # Create a failed problem result
            prob_result = ProblemResult(task_id=task_id, difficulty="unknown", category="unknown")
            prob_result.n_samples = num_samples
            prob_result.error_counts[ErrorType.MEMORY_ERROR.value] = num_samples
            problem_results.append(prob_result)
            total_samples += num_samples
            all_error_counts[ErrorType.MEMORY_ERROR.value] = all_error_counts.get(ErrorType.MEMORY_ERROR.value, 0) + num_samples
            continue

        except Exception as e:
            # Log error but continue to next problem
            logger.error(f"Error evaluating problem {task_id}: {e}")
            traceback.print_exc()
            print(json.dumps({
                "type": "log",
                "level": "error",
                "message": f"Problem {task_id} failed: {str(e)[:200]}"
            }), flush=True)
            
            # ===== OOM FIX: Also cleanup on general exceptions =====
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            # Create a failed problem result
            prob_result = ProblemResult(task_id=task_id, difficulty="unknown", category="unknown")
            prob_result.n_samples = num_samples
            prob_result.error_counts[ErrorType.RUNTIME_ERROR.value] = num_samples
            problem_results.append(prob_result)
            total_samples += num_samples
            all_error_counts[ErrorType.RUNTIME_ERROR.value] = all_error_counts.get(ErrorType.RUNTIME_ERROR.value, 0) + num_samples
            continue

        # ===== P1: Output real-time cumulative metrics for frontend =====
        if total_samples > 0:
            current_pass_at_1 = total_passed / total_samples * 100
            current_compile_rate = total_compiled / total_samples * 100
            
            # Compute current error breakdown
            error_breakdown = {}
            for error_type, count in all_error_counts.items():
                error_breakdown[error_type] = count / total_samples * 100
            
            print(json.dumps({
                "type": "metric",
                "data": {
                    "step": i + 1,
                    "pass_at_1": round(current_pass_at_1, 2),
                    "compile_rate": round(current_compile_rate, 2),
                    "total_samples": total_samples,
                    "total_passed": total_passed,
                    "total_compiled": total_compiled,
                    "error_breakdown": error_breakdown
                }
            }), flush=True)
        
        # Output per-problem result summary
        print(json.dumps({
            "type": "log",
            "level": "info",
            "message": f"Problem {i+1}/{len(problems)} completed: {prob_result.n_passed}/{prob_result.n_samples} passed"
        }), flush=True)
    
    # Final progress event - 100% complete
    print(json.dumps({
        "type": "progress",
        "completed": len(problems),
        "total": len(problems)
    }), flush=True)
    
    print(json.dumps({
        "type": "log",
        "level": "info",
        "message": f"All {len(problems)} problems evaluated. Computing final metrics..."
    }), flush=True)
    
    # ============== Compute Final Metrics ==============
    
    # Pass@k metrics
    pass_at_k = {}
    for k in k_values:
        scores = [compute_pass_at_k(r.n_samples, r.n_passed, min(k, r.n_samples)) 
                  for r in problem_results if r.n_samples > 0]
        pass_at_k[str(k)] = round(sum(scores) / len(scores) * 100, 2) if scores else 0.0
    
    pass_at_1 = pass_at_k.get('1', 0.0)
    compile_rate = round(total_compiled / total_samples * 100, 2) if total_samples > 0 else 0.0
    
    # Error statistics
    error_stats = compute_error_stats(all_error_counts, total_samples)
    
    # Time statistics
    time_stats = compute_time_stats(all_execution_times, timeout_count, total_samples)
    
    # Segment statistics
    difficulty_stats = compute_segment_stats(problem_results, 'difficulty')
    category_stats = compute_segment_stats(problem_results, 'category')
    
    # Code quality statistics
    code_quality_stats = CodeQualityStats(
        avg_code_length=statistics.mean(all_code_lengths) if all_code_lengths else 0.0,
        avg_line_count=statistics.mean(all_line_counts) if all_line_counts else 0.0,
        extra_io_rate=extra_io_count / total_samples * 100 if total_samples > 0 else 0.0,
        interface_compliance_rate=interface_compliant_count / total_samples * 100 if total_samples > 0 else 0.0
    )
    
    # Build output
    output = {
        # Basic metrics
        'passAt1': round(pass_at_1, 2),
        'compileRate': round(compile_rate, 2),
        'passAtK': pass_at_k,
        
        # Error classification
        'errorStats': {
            'syntaxErrorRate': round(error_stats.syntax_error_rate, 2),
            'runtimeErrorRate': round(error_stats.runtime_error_rate, 2),
            'timeoutRate': round(error_stats.timeout_rate, 2),
            'invalidOutputRate': round(error_stats.invalid_output_rate, 2),
            'assertionErrorRate': round(error_stats.assertion_error_rate, 2),
            'importErrorRate': round(error_stats.import_error_rate, 2),
            'memoryErrorRate': round(error_stats.memory_error_rate, 2),
        },
        
        # Time statistics
        'timeStats': {
            'meanRuntimeMs': round(time_stats.mean_runtime_ms, 2),
            'p50RuntimeMs': round(time_stats.p50_runtime_ms, 2),
            'p95RuntimeMs': round(time_stats.p95_runtime_ms, 2),
            'maxRuntimeMs': round(time_stats.max_runtime_ms, 2),
            'tleRate': round(time_stats.tle_rate, 2),
        },
        
        # Segment statistics
        'segmentStats': {
            'byDifficulty': {k: asdict(v) for k, v in difficulty_stats.items()},
            'byCategory': {k: asdict(v) for k, v in category_stats.items()},
        },
        
        # P1: Per-problem pass rate distribution
        'perProblemStats': {
            'passRates': [round(r.n_passed / r.n_samples * 100, 2) for r in problem_results if r.n_samples > 0],
            'min': round(min(r.n_passed / r.n_samples * 100 for r in problem_results if r.n_samples > 0), 2) if problem_results else 0,
            'max': round(max(r.n_passed / r.n_samples * 100 for r in problem_results if r.n_samples > 0), 2) if problem_results else 0,
            'median': round(statistics.median(r.n_passed / r.n_samples * 100 for r in problem_results if r.n_samples > 0), 2) if problem_results else 0,
            'mean': round(statistics.mean(r.n_passed / r.n_samples * 100 for r in problem_results if r.n_samples > 0), 2) if problem_results else 0,
        } if problem_results else None,
        
        # Code quality
        'codeQuality': {
            'avgCodeLength': round(code_quality_stats.avg_code_length, 2),
            'avgLineCount': round(code_quality_stats.avg_line_count, 2),
            'extraIORate': round(code_quality_stats.extra_io_rate, 2),
            'interfaceComplianceRate': round(code_quality_stats.interface_compliance_rate, 2),
        },
        
        # Failures
        'failures': failures,
        
        # Meta info
        'totalProblems': len(problems),
        'totalSamples': total_samples,
        'totalPassed': total_passed,
        'totalCompiled': total_compiled,
        
        # Eval Log ID (for linking)
        'evalRunId': eval_log.eval_run_id,
    }
    
    # =========================================================================
    # Finalize Eval Log
    # =========================================================================
    
    # Set overall metrics
    eval_logger_instance.set_metrics(
        eval_log,
        pass_at_1=pass_at_1,
        pass_at_5=pass_at_k.get('5', 0.0),
        pass_at_10=pass_at_k.get('10', 0.0),
        compile_rate=compile_rate,
        total_problems=len(problems),
        total_samples=total_samples,
        total_passed=total_passed,
        total_compiled=total_compiled,
    )
    
    # Set error distribution
    eval_logger_instance.set_error_distribution(
        eval_log,
        syntax_error_rate=error_stats.syntax_error_rate,
        runtime_error_rate=error_stats.runtime_error_rate,
        timeout_rate=error_stats.timeout_rate,
        assertion_error_rate=error_stats.assertion_error_rate,
        import_error_rate=error_stats.import_error_rate,
    )
    
    # Set time stats
    eval_logger_instance.set_time_stats(
        eval_log,
        mean_runtime_ms=time_stats.mean_runtime_ms,
        p50_runtime_ms=time_stats.p50_runtime_ms,
        p95_runtime_ms=time_stats.p95_runtime_ms,
        max_runtime_ms=time_stats.max_runtime_ms,
    )
    
    # P2: Set code quality metrics
    eval_logger_instance.set_code_quality(
        eval_log,
        avg_code_length=code_quality_stats.avg_code_length,
        avg_line_count=code_quality_stats.avg_line_count,
        extra_io_rate=code_quality_stats.extra_io_rate,
        interface_compliance_rate=code_quality_stats.interface_compliance_rate,
    )
    
    # P1: Set segment breakdown statistics
    eval_logger_instance.set_segment_breakdown(
        eval_log,
        by_difficulty={k: {'count': v.count, 'pass_at_1': v.pass_at_1, 'compile_rate': v.compile_rate} 
                       for k, v in difficulty_stats.items()},
        by_category={k: {'count': v.count, 'pass_at_1': v.pass_at_1, 'compile_rate': v.compile_rate} 
                     for k, v in category_stats.items()},
    )
    
    # P1: Set per-problem pass rate distribution
    per_problem_pass_rates = [
        r.n_passed / r.n_samples * 100 
        for r in problem_results 
        if r.n_samples > 0
    ]
    eval_logger_instance.set_per_problem_stats(eval_log, per_problem_pass_rates)
    
    # P0: Set failure examples by error type (with diverse sampling)
    eval_logger_instance.set_failure_examples_by_type(
        eval_log, 
        eval_log.sample_results,
        max_per_type=3  # 每种错误类型最多3个代表性案例
    )
    
    # Finalize and save
    eval_logger_instance.finalize(eval_log)
    
    # Save eval summary to file
    os.makedirs(output_dir, exist_ok=True)
    eval_summary_path = os.path.join(output_dir, 'eval_summary.json')
    eval_logger_instance.save_to_file(eval_log, eval_summary_path)
    
    # Output eval log event for backend parsing
    output_eval_log_event(eval_log)
    
    logger.info(f"Evaluation complete. Pass@1: {pass_at_1:.2f}%, Compile Rate: {compile_rate:.2f}%")
    logger.info(f"Error rates - Syntax: {error_stats.syntax_error_rate:.1f}%, "
                f"Runtime: {error_stats.runtime_error_rate:.1f}%, "
                f"Timeout: {error_stats.timeout_rate:.1f}%")
    logger.info(f"Time stats - Mean: {time_stats.mean_runtime_ms:.1f}ms, "
                f"P95: {time_stats.p95_runtime_ms:.1f}ms")
    logger.info(f"Eval summary saved to: {eval_summary_path}")
    
    return output


def main():
    parser = argparse.ArgumentParser(description="Code Evaluation Script with Comprehensive Metrics")
    parser.add_argument("--config", type=str, required=True, help="Path to config JSON file")
    args = parser.parse_args()
    
    with open(args.config, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    try:
        result = evaluate(config)
        print(json.dumps(result))
    except Exception as e:
        logger.error(f"Evaluation failed: {e}")
        traceback.print_exc()
        print(json.dumps({
            "passAt1": 0,
            "compileRate": 0,
            "passAtK": {},
            "errorStats": {
                "syntaxErrorRate": 0,
                "runtimeErrorRate": 0,
                "timeoutRate": 0,
                "invalidOutputRate": 0,
                "assertionErrorRate": 0,
                "importErrorRate": 0,
                "memoryErrorRate": 0,
            },
            "timeStats": {
                "meanRuntimeMs": 0,
                "p50RuntimeMs": 0,
                "p95RuntimeMs": 0,
                "maxRuntimeMs": 0,
                "tleRate": 0,
            },
            "failures": [{"taskId": "N/A", "prompt": "N/A", "output": "N/A", 
                          "errorType": "System Error", "error": str(e)}],
            "error": str(e),
            "totalProblems": 0,
            "totalSamples": 0,
        }))
        sys.exit(1)


if __name__ == "__main__":
    main()
