"""
Code Post-processing Main Pipeline
Integrates all modules to implement complete "self-healing flow"
"""

import time
import logging
from typing import Optional, Tuple

from .types import (
    PipelineConfig,
    PipelineResult,
    PhaseResult,
    ErrorType,
)
from .extractor import CodeExtractor
from .normalizer import CodeNormalizer
from .validator import CodeValidator
from .executor import CodeExecutor
from .fixer import RuleFixer

logger = logging.getLogger(__name__)


class CodePipeline:
    """
    LLM Code Post-processing Main Pipeline
    
    Processing Flow:
    1. Extract - Code extraction
    2. Normalize - Interface normalization
    3. Validate - Static validation
    4. Execute - Run tests
    5. Fix Loop - Fix loop
    
    Reference LeoLLM's 14-phase processing pipeline design
    """
    
    def __init__(self, config: Optional[PipelineConfig] = None):
        """
        Initialize pipeline
        
        Args:
            config: Pipeline configuration
        """
        self.config = config or PipelineConfig()
        
        # Initialize modules
        self.extractor = CodeExtractor()
        self.normalizer = CodeNormalizer()
        self.validator = CodeValidator()
        self.executor = CodeExecutor(timeout=self.config.execution_timeout)
        self.fixer = RuleFixer()
    
    def process(
        self,
        raw_output: str,
        test_code: str = "",
        signature: Optional[str] = None
    ) -> PipelineResult:
        """
        Execute complete post-processing flow
        
        Args:
            raw_output: LLM's raw output
            test_code: Test code
            signature: Expected function signature
            
        Returns:
            Processing result
        """
        start_time = time.perf_counter()
        signature = signature or self.config.default_signature
        
        # Initialize result
        result = PipelineResult(
            success=False,
            final_code="",
            original_code=raw_output,
        )
        
        current_code = raw_output
        
        try:
            # ================================================================
            # Phase 1: Extract - Code extraction
            # ================================================================
            if self.config.enable_extract:
                result.add_log("Phase 1: Code extraction")
                current_code = self.extractor.extract(current_code)
                result.phases_completed.append("extract")
                result.phase_results.append(PhaseResult(
                    phase_name="extract",
                    success=True,
                    code=current_code,
                ))
            
            if not current_code.strip():
                result.error_type = ErrorType.SYNTAX_ERROR
                result.error_message = "Code is empty after extraction"
                result.final_code = self._create_fallback(signature)
                return self._finalize_result(result, start_time)
            
            # ================================================================
            # Phase 2: Normalize - Interface normalization
            # ================================================================
            if self.config.enable_normalize:
                result.add_log("Phase 2: Interface normalization")
                current_code = self.normalizer.normalize(
                    current_code, signature, self.config.function_name
                )
                result.phases_completed.append("normalize")
                result.phase_results.append(PhaseResult(
                    phase_name="normalize",
                    success=True,
                    code=current_code,
                ))
            
            # ================================================================
            # Phase 3: Validate - Static validation
            # ================================================================
            if self.config.enable_validate:
                result.add_log("Phase 3: Static validation")
                valid, error_type, error_msg = self.validator.validate(
                    current_code, self.config.function_name
                )
                
                if not valid:
                    result.add_log(f"Validation failed: {error_type} - {error_msg}")
                    
                    # Try rule-based fix
                    if self.config.enable_rule_fix:
                        current_code, fixes = self._run_fix_loop(
                            current_code, error_type, error_msg, signature, result
                        )
                        
                        # Re-validate
                        valid, error_type, error_msg = self.validator.validate(
                            current_code, self.config.function_name
                        )
                
                result.phases_completed.append("validate")
                result.phase_results.append(PhaseResult(
                    phase_name="validate",
                    success=valid,
                    code=current_code,
                    error_type=error_type,
                    error_message=error_msg,
                ))
                
                if not valid:
                    result.error_type = error_type
                    result.error_message = error_msg
                    # Try to generate fallback code
                    current_code = self.fixer.generate_fallback(current_code, signature)
            
            # ================================================================
            # Phase 4: Execute - Run tests (if test code exists)
            # ================================================================
            if test_code:
                result.add_log("Phase 4: Run tests")
                exec_result = self.executor.execute_with_tests(current_code, test_code)
                
                result.execution_time_ms = exec_result.execution_time_ms
                result.phases_completed.append("execute")
                result.phase_results.append(PhaseResult(
                    phase_name="execute",
                    success=exec_result.passed,
                    code=current_code,
                    error_type=exec_result.error_type if not exec_result.passed else None,
                    error_message=exec_result.error_message if not exec_result.passed else None,
                ))
                
                if not exec_result.passed:
                    result.add_log(f"Test failed: {exec_result.error_type} - {exec_result.error_message}")
                    
                    # Try to fix
                    if self.config.enable_rule_fix:
                        current_code, fixes = self._run_fix_loop(
                            current_code, 
                            exec_result.error_type, 
                            exec_result.error_message, 
                            signature, 
                            result
                        )
                        
                        # Re-test
                        exec_result = self.executor.execute_with_tests(current_code, test_code)
                        result.add_log(f"Re-test: {'Passed' if exec_result.passed else 'Failed'}")
                        
                        if exec_result.passed:
                            result.success = True
                        else:
                            result.error_type = exec_result.error_type
                            result.error_message = exec_result.error_message
                    else:
                        result.error_type = exec_result.error_type
                        result.error_message = exec_result.error_message
                else:
                    result.success = True
            else:
                # No test code, only do static validation
                try:
                    import ast
                    ast.parse(current_code)
                    result.success = True
                except SyntaxError as e:
                    result.success = False
                    result.error_type = ErrorType.SYNTAX_ERROR
                    result.error_message = str(e)
            
            result.final_code = current_code
            
        except Exception as e:
            logger.exception("Pipeline processing exception")
            result.error_type = ErrorType.RUNTIME_ERROR
            result.error_message = str(e)
            result.final_code = current_code or self._create_fallback(signature)
        
        return self._finalize_result(result, start_time)
    
    def _run_fix_loop(
        self,
        code: str,
        error_type: ErrorType,
        error_message: str,
        signature: str,
        result: PipelineResult
    ) -> Tuple[str, list]:
        """
        Run fix loop
        """
        all_fixes = []
        
        for attempt in range(self.config.max_rule_fix_attempts):
            result.add_log(f"Fix attempt {attempt + 1}/{self.config.max_rule_fix_attempts}")
            result.rule_fix_attempts += 1
            
            code, fixes = self.fixer.fix(code, error_type, error_message, signature)
            all_fixes.extend(fixes)
            
            if fixes:
                result.add_log(f"Applied fixes: {', '.join(fixes)}")
                result.fixes_applied.extend(fixes)
            
            # Check if fix succeeded
            valid, new_error_type, new_error_msg = self.validator.validate(
                code, self.config.function_name
            )
            
            if valid:
                result.add_log("Fix successful")
                break
            
            error_type = new_error_type
            error_message = new_error_msg
        
        return code, all_fixes
    
    def _create_fallback(self, signature: str) -> str:
        """Create fallback code"""
        sig = signature.strip()
        if not sig.endswith(':'):
            sig += ':'
        return f"{sig}\n    return 0\n"
    
    def _finalize_result(self, result: PipelineResult, start_time: float) -> PipelineResult:
        """Finalize result processing"""
        result.total_time_ms = (time.perf_counter() - start_time) * 1000
        return result
    
    def process_batch(
        self,
        outputs: list,
        test_codes: Optional[list] = None,
        signature: Optional[str] = None
    ) -> list:
        """
        Batch process multiple outputs
        
        Args:
            outputs: LLM output list
            test_codes: Corresponding test code list
            signature: Function signature
            
        Returns:
            List of processing results
        """
        test_codes = test_codes or [""] * len(outputs)
        results = []
        
        for i, (output, test_code) in enumerate(zip(outputs, test_codes)):
            logger.info(f"Processing {i + 1}/{len(outputs)}")
            result = self.process(output, test_code, signature)
            results.append(result)
        
        return results
    
    def get_statistics(self, results: list) -> dict:
        """
        Calculate processing statistics
        
        Args:
            results: PipelineResult list
            
        Returns:
            Statistics dictionary
        """
        if not results:
            return {}
        
        total = len(results)
        success_count = sum(1 for r in results if r.success)
        
        # Error category statistics
        error_counts = {}
        for r in results:
            if r.error_type:
                error_name = r.error_type.value
                error_counts[error_name] = error_counts.get(error_name, 0) + 1
        
        # Fix statistics
        total_fixes = sum(len(r.fixes_applied) for r in results)
        fix_attempts = sum(r.rule_fix_attempts for r in results)
        
        # Time statistics
        total_times = [r.total_time_ms for r in results if r.total_time_ms > 0]
        
        return {
            "total_samples": total,
            "success_count": success_count,
            "success_rate": success_count / total * 100 if total > 0 else 0,
            "error_counts": error_counts,
            "total_fixes_applied": total_fixes,
            "total_fix_attempts": fix_attempts,
            "avg_time_ms": sum(total_times) / len(total_times) if total_times else 0,
        }


def create_pipeline(
    max_rule_fix: int = 2,
    timeout: int = 10,
    enable_fuzzing: bool = False,
    default_signature: str = "def solve(nums: list[int]) -> int:"
) -> CodePipeline:
    """
    Convenience function: Create pipeline instance
    """
    config = PipelineConfig(
        max_rule_fix_attempts=max_rule_fix,
        execution_timeout=timeout,
        enable_fuzzing=enable_fuzzing,
        default_signature=default_signature,
    )
    return CodePipeline(config)
