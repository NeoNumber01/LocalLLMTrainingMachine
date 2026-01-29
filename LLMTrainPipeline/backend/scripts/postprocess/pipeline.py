"""
代码后处理主管线
整合所有模块，实现完整的"自愈流程"
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
    LLM 代码后处理主管线
    
    处理流程：
    1. Extract - 代码抽取
    2. Normalize - 接口规范化
    3. Validate - 静态验证
    4. Execute - 运行测试
    5. Fix Loop - 修复循环
    
    参考 LeoLLM 的 14 阶段处理管线设计
    """
    
    def __init__(self, config: Optional[PipelineConfig] = None):
        """
        初始化管线
        
        Args:
            config: 管线配置
        """
        self.config = config or PipelineConfig()
        
        # 初始化各模块
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
        执行完整的后处理流程
        
        Args:
            raw_output: LLM 的原始输出
            test_code: 测试代码
            signature: 期望的函数签名
            
        Returns:
            处理结果
        """
        start_time = time.perf_counter()
        signature = signature or self.config.default_signature
        
        # 初始化结果
        result = PipelineResult(
            success=False,
            final_code="",
            original_code=raw_output,
        )
        
        current_code = raw_output
        
        try:
            # ================================================================
            # Phase 1: Extract - 代码抽取
            # ================================================================
            if self.config.enable_extract:
                result.add_log("Phase 1: 代码抽取")
                current_code = self.extractor.extract(current_code)
                result.phases_completed.append("extract")
                result.phase_results.append(PhaseResult(
                    phase_name="extract",
                    success=True,
                    code=current_code,
                ))
            
            if not current_code.strip():
                result.error_type = ErrorType.SYNTAX_ERROR
                result.error_message = "抽取后代码为空"
                result.final_code = self._create_fallback(signature)
                return self._finalize_result(result, start_time)
            
            # ================================================================
            # Phase 2: Normalize - 接口规范化
            # ================================================================
            if self.config.enable_normalize:
                result.add_log("Phase 2: 接口规范化")
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
            # Phase 3: Validate - 静态验证
            # ================================================================
            if self.config.enable_validate:
                result.add_log("Phase 3: 静态验证")
                valid, error_type, error_msg = self.validator.validate(
                    current_code, self.config.function_name
                )
                
                if not valid:
                    result.add_log(f"验证失败: {error_type} - {error_msg}")
                    
                    # 尝试规则修复
                    if self.config.enable_rule_fix:
                        current_code, fixes = self._run_fix_loop(
                            current_code, error_type, error_msg, signature, result
                        )
                        
                        # 重新验证
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
                    # 尝试生成回退代码
                    current_code = self.fixer.generate_fallback(current_code, signature)
            
            # ================================================================
            # Phase 4: Execute - 运行测试（如果有测试代码）
            # ================================================================
            if test_code:
                result.add_log("Phase 4: 运行测试")
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
                    result.add_log(f"测试失败: {exec_result.error_type} - {exec_result.error_message}")
                    
                    # 尝试修复
                    if self.config.enable_rule_fix:
                        current_code, fixes = self._run_fix_loop(
                            current_code, 
                            exec_result.error_type, 
                            exec_result.error_message, 
                            signature, 
                            result
                        )
                        
                        # 重新测试
                        exec_result = self.executor.execute_with_tests(current_code, test_code)
                        result.add_log(f"重新测试: {'通过' if exec_result.passed else '失败'}")
                        
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
                # 没有测试代码，只做静态验证
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
            logger.exception("管线处理异常")
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
        运行修复循环
        """
        all_fixes = []
        
        for attempt in range(self.config.max_rule_fix_attempts):
            result.add_log(f"修复尝试 {attempt + 1}/{self.config.max_rule_fix_attempts}")
            result.rule_fix_attempts += 1
            
            code, fixes = self.fixer.fix(code, error_type, error_message, signature)
            all_fixes.extend(fixes)
            
            if fixes:
                result.add_log(f"应用修复: {', '.join(fixes)}")
                result.fixes_applied.extend(fixes)
            
            # 检查是否修复成功
            valid, new_error_type, new_error_msg = self.validator.validate(
                code, self.config.function_name
            )
            
            if valid:
                result.add_log("修复成功")
                break
            
            error_type = new_error_type
            error_message = new_error_msg
        
        return code, all_fixes
    
    def _create_fallback(self, signature: str) -> str:
        """创建回退代码"""
        sig = signature.strip()
        if not sig.endswith(':'):
            sig += ':'
        return f"{sig}\n    return 0\n"
    
    def _finalize_result(self, result: PipelineResult, start_time: float) -> PipelineResult:
        """完成结果处理"""
        result.total_time_ms = (time.perf_counter() - start_time) * 1000
        return result
    
    def process_batch(
        self,
        outputs: list,
        test_codes: Optional[list] = None,
        signature: Optional[str] = None
    ) -> list:
        """
        批量处理多个输出
        
        Args:
            outputs: LLM 输出列表
            test_codes: 对应的测试代码列表
            signature: 函数签名
            
        Returns:
            处理结果列表
        """
        test_codes = test_codes or [""] * len(outputs)
        results = []
        
        for i, (output, test_code) in enumerate(zip(outputs, test_codes)):
            logger.info(f"处理 {i + 1}/{len(outputs)}")
            result = self.process(output, test_code, signature)
            results.append(result)
        
        return results
    
    def get_statistics(self, results: list) -> dict:
        """
        计算处理统计信息
        
        Args:
            results: PipelineResult 列表
            
        Returns:
            统计信息字典
        """
        if not results:
            return {}
        
        total = len(results)
        success_count = sum(1 for r in results if r.success)
        
        # 错误分类统计
        error_counts = {}
        for r in results:
            if r.error_type:
                error_name = r.error_type.value
                error_counts[error_name] = error_counts.get(error_name, 0) + 1
        
        # 修复统计
        total_fixes = sum(len(r.fixes_applied) for r in results)
        fix_attempts = sum(r.rule_fix_attempts for r in results)
        
        # 时间统计
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
    便捷函数：创建管线实例
    """
    config = PipelineConfig(
        max_rule_fix_attempts=max_rule_fix,
        execution_timeout=timeout,
        enable_fuzzing=enable_fuzzing,
        default_signature=default_signature,
    )
    return CodePipeline(config)
