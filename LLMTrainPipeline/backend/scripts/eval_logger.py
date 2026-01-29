#!/usr/bin/env python3
"""
Evaluation Logger - 收集评测元信息用于学术论文

功能:
- 收集评测运行元信息 (eval run ID, 时间, seed, git commit)
- 收集模型checkpoint信息
- 收集环境和硬件信息
- 收集生成配置 (temperature, top_p, k)
- 收集判题配置 (timeout, sandbox)
- 收集数据集信息 (split, 样本数, 难度分布)
- 收集样本级证据 (prompt, code, verdict)
- 收集后处理统计

Usage:
    from eval_logger import EvalLogger
    
    logger = EvalLogger()
    eval_log = logger.create_eval_log(
        eval_run_id="eval_run_2026_01_18_001",
        seed=42,
        base_model_name="Qwen/Qwen2.5-Coder-1.5B",
        checkpoint_path="/path/to/checkpoint",
    )
    # ... 评测过程 ...
    logger.add_sample_result(eval_log, sample_result)
    logger.finalize(eval_log)
    logger.save_to_file(eval_log, "output/eval_summary.json")
"""

import os
import sys
import json
import platform
import subprocess
import hashlib
import logging
from datetime import datetime
from dataclasses import dataclass, asdict, field
from typing import Optional, Dict, Any, List, Tuple

logger = logging.getLogger("EvalLogger")


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class EvalEnvironmentInfo:
    """评测环境信息"""
    os_version: str
    python_version: str
    pytorch_version: str
    transformers_version: str
    peft_version: Optional[str] = None
    vllm_version: Optional[str] = None
    gpu_model: Optional[str] = None
    gpu_memory_gb: Optional[float] = None
    cpu_model: Optional[str] = None
    ram_gb: Optional[float] = None


@dataclass
class GenerationSettings:
    """生成/解码配置"""
    k: int = 10                          # pass@k 的 k
    temperature: float = 0.8
    top_p: float = 0.95
    top_k: Optional[int] = None
    max_new_tokens: int = 512
    do_sample: bool = True
    stop_sequences: List[str] = field(default_factory=lambda: ["```"])
    repetition_penalty: Optional[float] = None
    prompt_template: str = "system/user/assistant"
    post_process_enabled: bool = True


@dataclass
class JudgeSettings:
    """判题配置"""
    timeout_seconds: int = 10
    memory_limit_mb: Optional[int] = None
    sandbox_mode: str = "subprocess"     # "subprocess" | "docker" | "none"
    recursion_limit: int = 1000
    network_disabled: bool = True
    file_access_disabled: bool = True
    python_version: str = ""


@dataclass
class DatasetInfo:
    """评测数据集信息"""
    dataset_name: str
    dataset_version: Optional[str] = None
    dataset_hash: Optional[str] = None
    split: str = "test"                  # "val" | "test"
    total_problems: int = 0
    total_samples: int = 0
    dedupe_rule: str = "by_problem_id"   # "by_problem_id" | "by_text_hash"
    difficulty_distribution: Dict[str, int] = field(default_factory=dict)
    category_distribution: Dict[str, int] = field(default_factory=dict)
    io_constraints: Optional[str] = None


@dataclass
class SampleResult:
    """样本级评测结果 (用于失败案例分析)"""
    task_id: str
    sample_index: int = 0
    difficulty: Optional[str] = None
    category: Optional[str] = None
    
    # 代码
    prompt: str = ""
    raw_output: str = ""
    post_process_output: Optional[str] = None
    
    # 执行结果
    traceback: Optional[str] = None
    failing_test_input: Optional[str] = None
    expected_output: Optional[str] = None
    actual_output: Optional[str] = None
    execution_time_ms: float = 0.0
    
    # 判定结果
    verdict: str = "CE"                  # "AC" | "WA" | "TLE" | "RE" | "CE"
    error_type: Optional[str] = None
    
    # 后处理追踪
    post_process_steps: List[str] = field(default_factory=list)
    post_process_rounds: int = 0
    was_fixed: bool = False


@dataclass
class PostProcessStats:
    """后处理统计"""
    enabled: bool = True
    total_attempts: int = 0
    successful_fixes: int = 0
    avg_fix_rounds: float = 0.0
    
    # 修复前后对比
    pass_at_1_before: float = 0.0
    pass_at_1_after: float = 0.0
    syntax_error_before: float = 0.0
    syntax_error_after: float = 0.0
    runtime_error_before: float = 0.0
    runtime_error_after: float = 0.0
    timeout_before: float = 0.0
    timeout_after: float = 0.0
    wrong_answer_before: float = 0.0
    wrong_answer_after: float = 0.0
    
    # 修复原因分布
    fix_reason_distribution: Dict[str, int] = field(default_factory=dict)


@dataclass
class MetricsOverall:
    """总体评测指标"""
    pass_at_1: float = 0.0
    pass_at_5: float = 0.0
    pass_at_10: float = 0.0
    compile_rate: float = 0.0
    total_problems: int = 0
    total_samples: int = 0
    total_passed: int = 0
    total_compiled: int = 0


@dataclass
class ErrorDistribution:
    """错误类型分布"""
    syntax_error_rate: float = 0.0
    indentation_error_rate: float = 0.0
    runtime_error_rate: float = 0.0
    timeout_rate: float = 0.0
    wrong_answer_rate: float = 0.0
    assertion_error_rate: float = 0.0
    import_error_rate: float = 0.0
    memory_error_rate: float = 0.0
    output_format_error_rate: float = 0.0


@dataclass
class TimeStats:
    """执行时间统计"""
    mean_runtime_ms: float = 0.0
    p50_runtime_ms: float = 0.0
    p95_runtime_ms: float = 0.0
    max_runtime_ms: float = 0.0


@dataclass
class SegmentBreakdown:
    """分段统计"""
    by_difficulty: Dict[str, Dict[str, float]] = field(default_factory=dict)
    by_category: Dict[str, Dict[str, float]] = field(default_factory=dict)


@dataclass
class PerProblemStats:
    """P1: 每题通过率分布统计"""
    min_pass_rate: float = 0.0       # 最低题目通过率
    max_pass_rate: float = 0.0       # 最高题目通过率
    median_pass_rate: float = 0.0    # 中位数题目通过率
    mean_pass_rate: float = 0.0      # 平均题目通过率
    std_pass_rate: float = 0.0       # 标准差
    total_problems: int = 0


@dataclass
class FailureExample:
    """P0: 单个失败案例"""
    task_id: str
    difficulty: Optional[str] = None
    category: Optional[str] = None
    prompt_preview: str = ""          # 完整 prompt
    output_preview: str = ""          # 完整 output
    traceback_preview: str = ""       # 完整 traceback
    error_type: str = ""
    verdict: str = ""


@dataclass
class FailureExamplesByType:
    """P0: 按错误类型分组的代表性失败案例"""
    syntax_error: List[FailureExample] = field(default_factory=list)
    runtime_error: List[FailureExample] = field(default_factory=list)
    assertion_error: List[FailureExample] = field(default_factory=list)
    timeout: List[FailureExample] = field(default_factory=list)
    import_error: List[FailureExample] = field(default_factory=list)
    wrong_answer: List[FailureExample] = field(default_factory=list)
    other: List[FailureExample] = field(default_factory=list)



@dataclass
class EvaluationProtocol:
    """评测方法论配置 - 用于明确 pass@k 计算口径"""
    # Pass@k 计算说明
    pass_at_k_definition: str = "success if any of the first k samples passes all tests"
    samples_per_task: int = 1  # numSamples (N)
    temperature: float = 0.2
    top_p: float = 0.95
    sorting_method: str = "generation_order"  # generation_order | logprob | random
    
    # Compile Rate 定义
    compile_rate_definition: str = "percentage of samples that run without SyntaxError during exec"
    
    # 超时和边界情况处理
    timeout_handling: str = "counted as failure (TLE)"
    memory_limit_handling: str = "counted as failure (MLE)"


@dataclass
class CodeQualityMetrics:
    """代码质量指标 - 展示在主报告中"""
    avg_code_length: float = 0.0
    avg_line_count: float = 0.0
    extra_io_rate: float = 0.0  # 包含 print/input 的比例
    interface_compliance_rate: float = 0.0  # 包含函数定义的比例


@dataclass
class ReproducibilityInfo:
    """可复现性信息"""
    python_seed: Optional[int] = None
    numpy_seed: Optional[int] = None
    torch_seed: Optional[int] = None
    evaluator_version: str = "1.0.0"
    checkpoint_hash: Optional[str] = None  # 模型文件的 MD5 前 8 位


@dataclass
class EvalSummary:
    """完整评测日志"""
    # 元信息
    eval_run_id: str
    eval_time: str
    seed: int
    git_commit: Optional[str]
    
    # 模型信息
    base_model_name: str
    checkpoint_path: str
    checkpoint_step: Optional[int] = None
    checkpoint_epoch: Optional[int] = None
    
    # 配置
    environment: Optional[EvalEnvironmentInfo] = None
    generation_config: Optional[GenerationSettings] = None
    judge_config: Optional[JudgeSettings] = None
    dataset_info: Optional[DatasetInfo] = None
    
    # P1: 评测方法论配置
    evaluation_protocol: Optional[EvaluationProtocol] = None
    
    # P1: 可复现性信息
    reproducibility_info: Optional[ReproducibilityInfo] = None
    
    # 指标
    metrics_overall: Optional[MetricsOverall] = None
    error_distribution: Optional[ErrorDistribution] = None
    time_stats: Optional[TimeStats] = None
    segment_breakdown: Optional[SegmentBreakdown] = None
    
    # P1: 每题通过率分布
    per_problem_stats: Optional[PerProblemStats] = None
    
    # P0: 按错误类型分组的代表性失败案例
    failure_examples_by_type: Optional[FailureExamplesByType] = None
    
    # P2: 代码质量指标
    code_quality: Optional[CodeQualityMetrics] = None
    
    # 后处理
    postprocess_stats: Optional[PostProcessStats] = None
    
    # 样本结果 (只保存失败+典型案例)
    sample_results: List[SampleResult] = field(default_factory=list)
    
    # 产物路径
    artifact_paths: Dict[str, str] = field(default_factory=dict)


# ============================================================================
# Eval Logger Class
# ============================================================================

class EvalLogger:
    """评测日志收集器"""
    
    @staticmethod
    def collect_environment() -> EvalEnvironmentInfo:
        """收集评测环境信息"""
        import importlib.metadata
        
        # OS version
        os_version = f"{platform.system()} {platform.release()}"
        
        # Python version
        python_version = platform.python_version()
        
        # PyTorch version
        try:
            import torch
            pytorch_version = torch.__version__
        except ImportError:
            pytorch_version = "N/A"
        
        # Transformers version
        try:
            transformers_version = importlib.metadata.version("transformers")
        except:
            transformers_version = "N/A"
        
        # PEFT version
        try:
            peft_version = importlib.metadata.version("peft")
        except:
            peft_version = None
        
        # vLLM version
        try:
            vllm_version = importlib.metadata.version("vllm")
        except:
            vllm_version = None
        
        # GPU info
        gpu_model = None
        gpu_memory_gb = None
        try:
            import torch
            if torch.cuda.is_available():
                gpu_model = torch.cuda.get_device_name(0)
                gpu_memory_gb = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
        except:
            pass
        
        # CPU info
        cpu_model = platform.processor() or "Unknown"
        
        # RAM info
        try:
            import psutil
            ram_gb = psutil.virtual_memory().total / (1024 ** 3)
        except:
            ram_gb = None
        
        return EvalEnvironmentInfo(
            os_version=os_version,
            python_version=python_version,
            pytorch_version=pytorch_version,
            transformers_version=transformers_version,
            peft_version=peft_version,
            vllm_version=vllm_version,
            gpu_model=gpu_model,
            gpu_memory_gb=round(gpu_memory_gb, 2) if gpu_memory_gb else None,
            cpu_model=cpu_model,
            ram_gb=round(ram_gb, 2) if ram_gb else None,
        )
    
    @staticmethod
    def get_git_commit() -> Optional[str]:
        """获取当前Git commit hash"""
        try:
            result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return result.stdout.strip()[:8]
        except:
            pass
        return None
    
    @staticmethod
    def compute_dataset_hash(dataset_path: str) -> Optional[str]:
        """计算数据集文件hash"""
        try:
            if os.path.isfile(dataset_path):
                with open(dataset_path, 'rb') as f:
                    return hashlib.md5(f.read()).hexdigest()[:8]
        except:
            pass
        return None
    
    @staticmethod
    def generate_eval_run_id() -> str:
        """生成评测运行ID"""
        return f"eval_run_{datetime.now().strftime('%Y_%m_%d_%H%M%S')}"
    
    def create_eval_log(
        self,
        eval_run_id: Optional[str] = None,
        seed: int = 42,
        base_model_name: str = "",
        checkpoint_path: str = "",
        checkpoint_step: Optional[int] = None,
        checkpoint_epoch: Optional[int] = None,
        generation_settings: Optional[GenerationSettings] = None,
        judge_settings: Optional[JudgeSettings] = None,
    ) -> EvalSummary:
        """创建新的评测日志"""
        if eval_run_id is None:
            eval_run_id = self.generate_eval_run_id()
        
        # 设置默认判题配置
        if judge_settings is None:
            judge_settings = JudgeSettings(python_version=platform.python_version())
        else:
            judge_settings.python_version = platform.python_version()
        
        log = EvalSummary(
            eval_run_id=eval_run_id,
            eval_time=datetime.now().isoformat(),
            seed=seed,
            git_commit=self.get_git_commit(),
            base_model_name=base_model_name,
            checkpoint_path=checkpoint_path,
            checkpoint_step=checkpoint_step,
            checkpoint_epoch=checkpoint_epoch,
            environment=self.collect_environment(),
            generation_config=generation_settings or GenerationSettings(),
            judge_config=judge_settings,
        )
        
        logger.info(f"Eval Log initialized: {eval_run_id}")
        logger.info(f"Seed: {seed}, Git commit: {log.git_commit or 'N/A'}")
        
        return log
    
    def set_dataset_info(
        self,
        log: EvalSummary,
        dataset_path: str,
        dataset_name: str,
        split: str = "test",
        total_problems: int = 0,
        total_samples: int = 0,
        difficulty_distribution: Optional[Dict[str, int]] = None,
        category_distribution: Optional[Dict[str, int]] = None,
    ) -> None:
        """设置数据集信息"""
        log.dataset_info = DatasetInfo(
            dataset_name=dataset_name,
            dataset_hash=self.compute_dataset_hash(dataset_path),
            split=split,
            total_problems=total_problems,
            total_samples=total_samples,
            difficulty_distribution=difficulty_distribution or {},
            category_distribution=category_distribution or {},
        )
    
    def add_sample_result(self, log: EvalSummary, result: SampleResult) -> None:
        """添加样本级结果"""
        log.sample_results.append(result)
    
    def set_metrics(
        self,
        log: EvalSummary,
        pass_at_1: float,
        pass_at_5: float = 0.0,
        pass_at_10: float = 0.0,
        compile_rate: float = 0.0,
        total_problems: int = 0,
        total_samples: int = 0,
        total_passed: int = 0,
        total_compiled: int = 0,
    ) -> None:
        """设置总体指标"""
        log.metrics_overall = MetricsOverall(
            pass_at_1=pass_at_1,
            pass_at_5=pass_at_5,
            pass_at_10=pass_at_10,
            compile_rate=compile_rate,
            total_problems=total_problems,
            total_samples=total_samples,
            total_passed=total_passed,
            total_compiled=total_compiled,
        )
    
    def set_error_distribution(
        self,
        log: EvalSummary,
        syntax_error_rate: float = 0.0,
        runtime_error_rate: float = 0.0,
        timeout_rate: float = 0.0,
        wrong_answer_rate: float = 0.0,
        assertion_error_rate: float = 0.0,
        import_error_rate: float = 0.0,
        **kwargs
    ) -> None:
        """设置错误分布"""
        log.error_distribution = ErrorDistribution(
            syntax_error_rate=syntax_error_rate,
            runtime_error_rate=runtime_error_rate,
            timeout_rate=timeout_rate,
            wrong_answer_rate=wrong_answer_rate,
            assertion_error_rate=assertion_error_rate,
            import_error_rate=import_error_rate,
            **kwargs
        )
    
    def set_time_stats(
        self,
        log: EvalSummary,
        mean_runtime_ms: float,
        p50_runtime_ms: float,
        p95_runtime_ms: float,
        max_runtime_ms: float,
    ) -> None:
        """设置时间统计"""
        log.time_stats = TimeStats(
            mean_runtime_ms=mean_runtime_ms,
            p50_runtime_ms=p50_runtime_ms,
            p95_runtime_ms=p95_runtime_ms,
            max_runtime_ms=max_runtime_ms,
        )
    
    def set_postprocess_stats(
        self,
        log: EvalSummary,
        enabled: bool,
        total_attempts: int,
        successful_fixes: int,
        pass_at_1_before: float,
        pass_at_1_after: float,
        fix_reason_distribution: Optional[Dict[str, int]] = None,
        **kwargs
    ) -> None:
        """设置后处理统计"""
        avg_fix_rounds = kwargs.get('avg_fix_rounds', 0.0)
        log.postprocess_stats = PostProcessStats(
            enabled=enabled,
            total_attempts=total_attempts,
            successful_fixes=successful_fixes,
            avg_fix_rounds=avg_fix_rounds,
            pass_at_1_before=pass_at_1_before,
            pass_at_1_after=pass_at_1_after,
            fix_reason_distribution=fix_reason_distribution or {},
            **{k: v for k, v in kwargs.items() if k != 'avg_fix_rounds'}
        )
    
    def set_evaluation_protocol(
        self,
        log: EvalSummary,
        samples_per_task: int,
        temperature: float,
        top_p: float = 0.95,
        sorting_method: str = "generation_order",
        pass_at_k_definition: str = "success if any of the first k samples passes all tests",
        compile_rate_definition: str = "percentage of samples that run without SyntaxError during exec",
        timeout_handling: str = "counted as failure (TLE)",
        memory_limit_handling: str = "counted as failure (MLE)",
    ) -> None:
        """P1: 设置评测方法论配置"""
        log.evaluation_protocol = EvaluationProtocol(
            pass_at_k_definition=pass_at_k_definition,
            samples_per_task=samples_per_task,
            temperature=temperature,
            top_p=top_p,
            sorting_method=sorting_method,
            compile_rate_definition=compile_rate_definition,
            timeout_handling=timeout_handling,
            memory_limit_handling=memory_limit_handling,
        )
    
    def set_reproducibility_info(
        self,
        log: EvalSummary,
        python_seed: Optional[int] = None,
        numpy_seed: Optional[int] = None,
        torch_seed: Optional[int] = None,
        evaluator_version: str = "1.0.0",
        checkpoint_hash: Optional[str] = None,
    ) -> None:
        """P1: 设置可复现性信息"""
        log.reproducibility_info = ReproducibilityInfo(
            python_seed=python_seed,
            numpy_seed=numpy_seed,
            torch_seed=torch_seed,
            evaluator_version=evaluator_version,
            checkpoint_hash=checkpoint_hash,
        )
    
    def set_code_quality(
        self,
        log: EvalSummary,
        avg_code_length: float,
        avg_line_count: float,
        extra_io_rate: float,
        interface_compliance_rate: float,
    ) -> None:
        """P2: 设置代码质量指标"""
        log.code_quality = CodeQualityMetrics(
            avg_code_length=avg_code_length,
            avg_line_count=avg_line_count,
            extra_io_rate=extra_io_rate,
            interface_compliance_rate=interface_compliance_rate,
        )
    
    def set_segment_breakdown(
        self,
        log: EvalSummary,
        by_difficulty: Dict[str, Dict[str, float]],
        by_category: Dict[str, Dict[str, float]],
    ) -> None:
        """P1: 设置分段统计"""
        log.segment_breakdown = SegmentBreakdown(
            by_difficulty=by_difficulty,
            by_category=by_category,
        )
    
    def set_per_problem_stats(
        self,
        log: EvalSummary,
        pass_rates: List[float],
    ) -> None:
        """P1: 设置每题通过率分布统计"""
        import statistics
        
        if not pass_rates:
            return
        
        log.per_problem_stats = PerProblemStats(
            min_pass_rate=round(min(pass_rates), 2),
            max_pass_rate=round(max(pass_rates), 2),
            median_pass_rate=round(statistics.median(pass_rates), 2),
            mean_pass_rate=round(statistics.mean(pass_rates), 2),
            std_pass_rate=round(statistics.stdev(pass_rates), 2) if len(pass_rates) > 1 else 0.0,
            total_problems=len(pass_rates),
        )
    
    def set_failure_examples_by_type(
        self,
        log: EvalSummary,
        sample_results: List[SampleResult],
        max_per_type: int = 3,
    ) -> None:
        """
        P0: 按错误类型分组设置代表性失败案例
        
        多样化采样策略:
        1. 优先选择不同 task_id 的样本（避免同题重复）
        2. 如果同类错误都来自同一题，则选择不同 sample_index
        3. 随机打乱以避免总是选择最先出现的样本
        """
        import random
        
        # 按错误类型分组失败样本
        failures_by_type: Dict[str, List[SampleResult]] = {
            'syntax_error': [],
            'runtime_error': [],
            'assertion_error': [],
            'timeout': [],
            'import_error': [],
            'wrong_answer': [],
            'other': [],
        }
        
        for sample in sample_results:
            if sample.verdict == 'AC':
                continue
            
            error_type = sample.error_type or ''
            
            # 映射错误类型到分组
            if 'syntax' in error_type.lower() or 'indentation' in error_type.lower():
                category = 'syntax_error'
            elif 'runtime' in error_type.lower() or 'name' in error_type.lower() or 'type' in error_type.lower():
                category = 'runtime_error'
            elif 'assertion' in error_type.lower():
                category = 'assertion_error'
            elif 'timeout' in error_type.lower() or sample.verdict == 'TLE':
                category = 'timeout'
            elif 'import' in error_type.lower() or 'module' in error_type.lower():
                category = 'import_error'
            elif sample.verdict == 'WA':
                category = 'wrong_answer'
            else:
                category = 'other'
            
            failures_by_type[category].append(sample)
        
        # 多样化采样
        result = FailureExamplesByType()
        
        for category, samples in failures_by_type.items():
            if not samples:
                continue
            
            # 随机打乱以避免总是选择同样的样本
            random.shuffle(samples)
            
            # 按 task_id 分组，优先选择不同题目的样本
            task_groups: Dict[str, List[SampleResult]] = {}
            for s in samples:
                if s.task_id not in task_groups:
                    task_groups[s.task_id] = []
                task_groups[s.task_id].append(s)
            
            # 轮询选择（确保多样性）
            selected: List[FailureExample] = []
            task_ids = list(task_groups.keys())
            random.shuffle(task_ids)
            
            idx = 0
            while len(selected) < max_per_type and task_ids:
                task_id = task_ids[idx % len(task_ids)]
                if task_groups[task_id]:
                    sample = task_groups[task_id].pop(0)
                    selected.append(FailureExample(
                        task_id=sample.task_id,
                        difficulty=sample.difficulty,
                        category=sample.category,
                        prompt_preview=sample.prompt,  # 完整保存，不截断
                        output_preview=sample.raw_output,  # 完整保存，不截断
                        traceback_preview=sample.traceback or '',  # 完整保存，不截断
                        error_type=sample.error_type or '',
                        verdict=sample.verdict,
                    ))
                    # 如果该 task_id 没有更多样本了，移除
                    if not task_groups[task_id]:
                        task_ids.remove(task_id)
                idx += 1
                if idx > len(samples):  # 防止无限循环
                    break
            
            # 设置到结果
            setattr(result, category, selected)
        
        log.failure_examples_by_type = result
    
    def finalize(self, log: EvalSummary) -> EvalSummary:
        """完成评测日志"""
        logger.info("=" * 60)
        logger.info("EVALUATION SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Eval Run ID: {log.eval_run_id}")
        logger.info(f"Seed: {log.seed}")
        logger.info(f"Model: {log.base_model_name}")
        
        if log.metrics_overall:
            logger.info(f"Pass@1: {log.metrics_overall.pass_at_1:.2f}%")
            logger.info(f"Pass@10: {log.metrics_overall.pass_at_10:.2f}%")
            logger.info(f"Compile Rate: {log.metrics_overall.compile_rate:.2f}%")
        
        if log.postprocess_stats and log.postprocess_stats.enabled:
            logger.info(f"Post-process: {log.postprocess_stats.pass_at_1_before:.2f}% -> "
                        f"{log.postprocess_stats.pass_at_1_after:.2f}%")
        
        logger.info("=" * 60)
        return log
    
    def save_to_file(self, log: EvalSummary, output_path: str) -> None:
        """保存日志到JSON文件"""
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(asdict(log), f, indent=2, ensure_ascii=False)
        
        logger.info(f"Eval summary saved to: {output_path}")
    
    def to_json(self, log: EvalSummary) -> str:
        """转换为JSON字符串"""
        return json.dumps(asdict(log), ensure_ascii=False)
    
    def to_dict(self, log: EvalSummary) -> dict:
        """转换为字典"""
        return asdict(log)


# ============================================================================
# Convenience Functions
# ============================================================================

def create_eval_log(**kwargs) -> EvalSummary:
    """快速创建评测日志的便捷函数"""
    return EvalLogger().create_eval_log(**kwargs)


def output_eval_log_event(log: EvalSummary):
    """输出评测日志事件到stdout供后端解析"""
    print(json.dumps({
        "type": "eval_log",
        "data": asdict(log)
    }))


if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.INFO)
    
    eval_logger = EvalLogger()
    log = eval_logger.create_eval_log(
        seed=42,
        base_model_name="Qwen/Qwen2.5-Coder-1.5B",
        checkpoint_path="/path/to/checkpoint",
    )
    
    # 设置数据集
    eval_logger.set_dataset_info(
        log,
        dataset_path="./data/test.jsonl",
        dataset_name="CodeEval-Test",
        split="test",
        total_problems=164,
        total_samples=1640,
    )
    
    # 设置指标
    eval_logger.set_metrics(
        log,
        pass_at_1=45.2,
        pass_at_5=62.1,
        pass_at_10=71.3,
        compile_rate=85.4,
        total_problems=164,
        total_samples=1640,
    )
    
    # 设置错误分布
    eval_logger.set_error_distribution(
        log,
        syntax_error_rate=5.2,
        runtime_error_rate=12.3,
        timeout_rate=2.1,
        wrong_answer_rate=35.2,
    )
    
    # 设置后处理统计
    eval_logger.set_postprocess_stats(
        log,
        enabled=True,
        total_attempts=500,
        successful_fixes=120,
        pass_at_1_before=42.1,
        pass_at_1_after=45.2,
    )
    
    # 完成
    eval_logger.finalize(log)
    
    print("\n--- JSON Output ---")
    print(eval_logger.to_json(log))
