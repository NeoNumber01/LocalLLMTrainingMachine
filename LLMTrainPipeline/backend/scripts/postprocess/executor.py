"""
Code Execution Module
Sandbox execution, pytest testing, error classification
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

# Default timeout
DEFAULT_TIMEOUT = 10


class CodeExecutor:
    """
    Code Executor
    
    Features:
    1. Sandbox execution (subprocess + timeout)
    2. pytest integration testing
    3. Error classification
    4. Boundary case testing
    """
    
    def __init__(self, timeout: int = DEFAULT_TIMEOUT):
        """
        Initialize executor
        
        Args:
            timeout: Execution timeout (seconds)
        """
        self.timeout = timeout
    
    def execute_with_tests(
        self,
        code: str,
        test_code: str,
        timeout: Optional[int] = None
    ) -> ExecutionResult:
        """
        Execute code and run tests
        
        Args:
            code: Code to execute
            test_code: Test code
            timeout: Timeout
            
        Returns:
            Execution result
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
        Execute tests using pytest
        
        Args:
            code: Code to test
            test_code: pytest format test code
            timeout: Timeout
            
        Returns:
            Execution result
        """
        timeout = timeout or self.timeout
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            
            # Write code file
            code_file = tmpdir_path / "solution.py"
            code_file.write_text(code, encoding="utf-8")
            
            # Write test file
            test_content = f"""
# Import the solution
from solution import solve

# Test code
{test_code}
"""
            test_file = tmpdir_path / "test_solution.py"
            test_file.write_text(test_content, encoding="utf-8")
            
            # Run pytest
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
                
                # Parse results
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
                    error_message=f"Execution timeout ({timeout}s)",
                    execution_time_ms=timeout * 1000,
                )
    
    def _run_in_subprocess(self, code: str, timeout: int) -> ExecutionResult:
        """
        Execute code in subprocess
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
                error_message=f"Execution timeout ({timeout}s)",
                execution_time_ms=timeout * 1000,
            )
        finally:
            try:
                os.unlink(temp_path)
            except:
                pass
    
    def _classify_error(self, error_output: str) -> ErrorType:
        """
        Classify error type based on error message
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
        Extract error message from output
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
        
        # Fallback: return last few non-empty lines
        non_empty = [l for l in lines if l.strip()]
        if non_empty:
            return ' | '.join(non_empty[-3:])[:200]
        
        return "Unknown error"
    
    def _parse_pytest_counts(self, output: str) -> Tuple[int, int]:
        """
        Parse test statistics from pytest output
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
        Run boundary case tests
        
        Returns:
            [(input, passed, error_message), ...]
        """
        boundary_cases = [
            [],           # Empty array
            [0],          # Single element
            [1],
            [-1],
            [0, 0],       # All same
            [1, 1, 1],
            [-1, -1],     # All negative
            list(range(100)),  # Large array
            list(range(100, 0, -1)),  # Decreasing
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
    Generate random test input
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
