"""
代码执行模块
沙箱执行、pytest 测试、错误分类
"""

import os
import sys
import subprocess
import tempfile
import time
import re
import logging
from pathlib import Path
from typing import Optional, Tuple, List, Any

from .types import ErrorType, ExecutionResult

logger = logging.getLogger(__name__)

# 默认超时时间
DEFAULT_TIMEOUT = 10


class CodeExecutor:
    """
    代码执行器
    
    功能：
    1. 沙箱执行（subprocess + timeout）
    2. pytest 集成测试
    3. 错误分类
    4. 边界用例测试
    """
    
    def __init__(self, timeout: int = DEFAULT_TIMEOUT):
        """
        初始化执行器
        
        Args:
            timeout: 执行超时时间（秒）
        """
        self.timeout = timeout
    
    def execute_with_tests(
        self,
        code: str,
        test_code: str,
        timeout: Optional[int] = None
    ) -> ExecutionResult:
        """
        执行代码并运行测试
        
        Args:
            code: 待执行代码
            test_code: 测试代码
            timeout: 超时时间
            
        Returns:
            执行结果
        """
        timeout = timeout or self.timeout
        
        full_code = code + "\n\n" + test_code
        
        try:
            return self._run_in_subprocess(full_code, timeout)
        except Exception as e:
            return ExecutionResult(
                passed=False,
                error_type=ErrorType.RUNTIME_ERROR,
                error_message=str(e)
            )
    
    def execute_with_pytest(
        self,
        code: str,
        test_code: str,
        timeout: Optional[int] = None
    ) -> ExecutionResult:
        """
        使用 pytest 执行测试
        
        Args:
            code: 待测试代码
            test_code: pytest 格式测试代码
            timeout: 超时时间
            
        Returns:
            执行结果
        """
        timeout = timeout or self.timeout
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            
            # 写入代码文件
            code_file = tmpdir_path / "solution.py"
            code_file.write_text(code, encoding="utf-8")
            
            # 写入测试文件
            test_content = f"""
# Import the solution
from solution import solve

# Test code
{test_code}
"""
            test_file = tmpdir_path / "test_solution.py"
            test_file.write_text(test_content, encoding="utf-8")
            
            # 运行 pytest
            start_time = time.perf_counter()
            
            try:
                proc = subprocess.run(
                    [sys.executable, "-m", "pytest", str(test_file), "-v", "--tb=short"],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=str(tmpdir_path),
                    env={**os.environ, "PYTHONPATH": str(tmpdir_path)},
                )
                
                execution_time_ms = (time.perf_counter() - start_time) * 1000
                
                # 解析结果
                if proc.returncode == 0:
                    passed, total = self._parse_pytest_counts(proc.stdout)
                    return ExecutionResult(
                        passed=True,
                        error_type=ErrorType.NONE,
                        execution_time_ms=execution_time_ms,
                        stdout=proc.stdout,
                        stderr=proc.stderr,
                        tests_passed=passed,
                        tests_total=total,
                    )
                else:
                    error_type = self._classify_error(proc.stdout + proc.stderr)
                    error_message = self._extract_error_message(proc.stdout + proc.stderr)
                    passed, total = self._parse_pytest_counts(proc.stdout)
                    
                    return ExecutionResult(
                        passed=False,
                        error_type=error_type,
                        error_message=error_message,
                        execution_time_ms=execution_time_ms,
                        stdout=proc.stdout,
                        stderr=proc.stderr,
                        tests_passed=passed,
                        tests_total=total,
                    )
                    
            except subprocess.TimeoutExpired:
                return ExecutionResult(
                    passed=False,
                    error_type=ErrorType.TIMEOUT,
                    error_message=f"执行超时 ({timeout}s)",
                    execution_time_ms=timeout * 1000,
                )
    
    def _run_in_subprocess(self, code: str, timeout: int) -> ExecutionResult:
        """
        在子进程中执行代码
        """
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write(code)
            temp_path = f.name
        
        try:
            start_time = time.perf_counter()
            
            result = subprocess.run(
                [sys.executable, temp_path],
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            execution_time_ms = (time.perf_counter() - start_time) * 1000
            
            if result.returncode == 0:
                return ExecutionResult(
                    passed=True,
                    error_type=ErrorType.NONE,
                    execution_time_ms=execution_time_ms,
                    stdout=result.stdout,
                    stderr=result.stderr,
                )
            else:
                error_type = self._classify_error(result.stderr or result.stdout)
                return ExecutionResult(
                    passed=False,
                    error_type=error_type,
                    error_message=(result.stderr or result.stdout)[:500],
                    execution_time_ms=execution_time_ms,
                    stdout=result.stdout,
                    stderr=result.stderr,
                )
                
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                passed=False,
                error_type=ErrorType.TIMEOUT,
                error_message=f"执行超时 ({timeout}s)",
                execution_time_ms=timeout * 1000,
            )
        finally:
            try:
                os.unlink(temp_path)
            except:
                pass
    
    def _classify_error(self, error_output: str) -> ErrorType:
        """
        根据错误信息分类错误类型
        """
        error_lower = error_output.lower()
        
        if "syntaxerror" in error_lower:
            return ErrorType.SYNTAX_ERROR
        elif "indentationerror" in error_lower:
            return ErrorType.INDENTATION_ERROR
        elif "importerror" in error_lower or "modulenotfounderror" in error_lower:
            return ErrorType.IMPORT_ERROR
        elif "nameerror" in error_lower:
            return ErrorType.NAME_ERROR
        elif "typeerror" in error_lower:
            return ErrorType.TYPE_ERROR
        elif "valueerror" in error_lower:
            return ErrorType.VALUE_ERROR
        elif "indexerror" in error_lower:
            return ErrorType.INDEX_ERROR
        elif "keyerror" in error_lower:
            return ErrorType.KEY_ERROR
        elif "attributeerror" in error_lower:
            return ErrorType.ATTRIBUTE_ERROR
        elif "recursionerror" in error_lower:
            return ErrorType.RECURSION_ERROR
        elif "memoryerror" in error_lower or "killed" in error_lower:
            return ErrorType.MEMORY_ERROR
        elif "assertionerror" in error_lower:
            return ErrorType.ASSERTION_ERROR
        elif "timeout" in error_lower or "timed out" in error_lower:
            return ErrorType.TIMEOUT
        else:
            return ErrorType.RUNTIME_ERROR
    
    def _extract_error_message(self, output: str) -> str:
        """
        从输出中提取错误消息
        """
        lines = output.split('\n')
        error_lines = []
        
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('E '):
                error_lines.append(stripped[2:])
            elif 'Error:' in stripped or 'Error(' in stripped:
                error_lines.append(stripped)
        
        if error_lines:
            message = ' | '.join(error_lines[:3])
            return message[:200]
        
        # 回退：返回最后几行非空行
        non_empty = [l for l in lines if l.strip()]
        if non_empty:
            return ' | '.join(non_empty[-3:])[:200]
        
        return "Unknown error"
    
    def _parse_pytest_counts(self, output: str) -> Tuple[int, int]:
        """
        解析 pytest 输出中的测试统计
        """
        passed_match = re.search(r'(\d+)\s+passed', output)
        failed_match = re.search(r'(\d+)\s+failed', output)
        error_match = re.search(r'(\d+)\s+error', output)
        
        passed = int(passed_match.group(1)) if passed_match else 0
        failed = int(failed_match.group(1)) if failed_match else 0
        errors = int(error_match.group(1)) if error_match else 0
        
        total = passed + failed + errors
        return passed, total
    
    def run_boundary_tests(
        self,
        code: str,
        function_name: str = "solve",
        timeout: int = 5
    ) -> List[Tuple[Any, bool, str]]:
        """
        运行边界用例测试
        
        Returns:
            [(输入, 是否通过, 错误信息), ...]
        """
        boundary_cases = [
            [],           # 空数组
            [0],          # 单元素
            [1],
            [-1],
            [0, 0],       # 全相同
            [1, 1, 1],
            [-1, -1],     # 全负数
            list(range(100)),  # 大数组
            list(range(100, 0, -1)),  # 递减
        ]
        
        results = []
        
        for case in boundary_cases:
            test_code = f"""
try:
    result = {function_name}({case!r})
    print("PASS:", result)
except Exception as e:
    print("FAIL:", type(e).__name__, str(e))
"""
            full_code = code + "\n\n" + test_code
            exec_result = self._run_in_subprocess(full_code, timeout)
            
            if exec_result.passed and "PASS:" in exec_result.stdout:
                results.append((case, True, ""))
            else:
                error_msg = exec_result.error_message or exec_result.stdout
                results.append((case, False, error_msg[:100]))
        
        return results


def generate_random_input(problem_type: str = "array", size: Optional[int] = None) -> Any:
    """
    生成随机测试输入
    """
    import random
    
    if problem_type == "array":
        size = size or random.randint(1, 100)
        return [random.randint(-1000, 1000) for _ in range(size)]
    elif problem_type == "string":
        size = size or random.randint(1, 50)
        return ''.join(random.choices('abcdefghijklmnopqrstuvwxyz', k=size))
    elif problem_type == "integer":
        return random.randint(-10**9, 10**9)
    elif problem_type == "matrix":
        rows = size or random.randint(1, 10)
        cols = random.randint(1, 10)
        return [[random.randint(-100, 100) for _ in range(cols)] for _ in range(rows)]
    else:
        return random.randint(1, 100)
