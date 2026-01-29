#!/usr/bin/env python3
"""
Evaluation Logger - Collect evaluation metadata for academic papers

Features:
- Collect evaluation run metadata (eval run ID, time, seed, git commit)
- Collect model checkpoint information
- Collect environment and hardware information
- Collect generation config (temperature, top_p, k)
- Collect judge config (timeout, sandbox)
- Collect dataset information (split, sample count, difficulty distribution)
- Collect sample-level evidence (prompt, code, verdict)
- Collect post-processing statistics

Usage:
    from eval_logger import EvalLogger
    
    logger = EvalLogger()
    eval_log = logger.create_eval_log(
        eval_run_id="eval_run_2026_01_18_001",
        seed=42,
        base_model_name="Qwen/Qwen2.5-Coder-1.5B",
        checkpoint_path="/path/to/checkpoint",
    )
    # ... evaluation process ...
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
    """Evaluation environment information"""
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
    """Generation/Decoding configuration"""
    k: int = 10                          # k for pass@k
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
    """Judge configuration"""
    timeout_seconds: int = 10
    memory_limit_mb: Optional[int] = None
    sandbox_mode: str = "subprocess"     # "subprocess" | "docker" | "none"
    recursion_limit: int = 1000
    network_disabled: bool = True
    file_access_disabled: bool = True
    python_version: str = ""


@dataclass
class DatasetInfo:
    """Evaluation dataset information"""
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
    """Sample-level evaluation result (for failure case analysis)"""
    task_id: str
    sample_index: int = 0
    difficulty: Optional[str] = None
    category: Optional[str] = None
    
    # Code
    prompt: str = ""
    raw_output: str = ""
    post_process_output: Optional[str] = None
    
    # Execution result
    traceback: Optional[str] = None
    failing_test_input: Optional[str] = None
    expected_output: Optional[str] = None
    actual_output: Optional[str] = None
    execution_time_ms: float = 0.0
    
    # Judgment result
    verdict: str = "CE"                  # "AC" | "WA" | "TLE" | "RE" | "CE"
    error_type: Optional[str] = None
    
    # Post-processing tracking
    post_process_steps: List[str] = field(default_factory=list)
    post_process_rounds: int = 0
    was_fixed: bool = False


@dataclass
class PostProcessStats:
    """Post-processing statistics"""
    enabled: bool = True
    total_attempts: int = 0
    successful_fixes: int = 0
    avg_fix_rounds: float = 0.0
    
    # Before/after fix comparison
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
    
    # Fix reason distribution
    fix_reason_distribution: Dict[str, int] = field(default_factory=dict)


@dataclass
class MetricsOverall:
    """Overall evaluation metrics"""
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
    """Error type distribution"""
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
    """Execution time statistics"""
    mean_runtime_ms: float = 0.0
    p50_runtime_ms: float = 0.0
    p95_runtime_ms: float = 0.0
    max_runtime_ms: float = 0.0


@dataclass
class SegmentBreakdown:
    """Segment statistics"""
    by_difficulty: Dict[str, Dict[str, float]] = field(default_factory=dict)
    by_category: Dict[str, Dict[str, float]] = field(default_factory=dict)


@dataclass
class PerProblemStats:
    """P1: Per-problem pass rate distribution statistics"""
    min_pass_rate: float = 0.0       # Minimum problem pass rate
    max_pass_rate: float = 0.0       # Maximum problem pass rate
    median_pass_rate: float = 0.0    # Median problem pass rate
    mean_pass_rate: float = 0.0      # Average problem pass rate
    std_pass_rate: float = 0.0       # Standard deviation
    total_problems: int = 0


@dataclass
class FailureExample:
    """P0: Single failure case"""
    task_id: str
    difficulty: Optional[str] = None
    category: Optional[str] = None
    prompt_preview: str = ""          # Complete prompt
    output_preview: str = ""          # Complete output
    traceback_preview: str = ""       # Complete traceback
    error_type: str = ""
    verdict: str = ""


@dataclass
class FailureExamplesByType:
    """P0: Representative failure cases grouped by error type"""
    syntax_error: List[FailureExample] = field(default_factory=list)
    runtime_error: List[FailureExample] = field(default_factory=list)
    assertion_error: List[FailureExample] = field(default_factory=list)
    timeout: List[FailureExample] = field(default_factory=list)
    import_error: List[FailureExample] = field(default_factory=list)
    wrong_answer: List[FailureExample] = field(default_factory=list)
    other: List[FailureExample] = field(default_factory=list)



@dataclass
class EvaluationProtocol:
    """Evaluation methodology configuration - used to clarify pass@k calculation standard"""
    # Pass@k calculation description
    pass_at_k_definition: str = "success if any of the first k samples passes all tests"
    samples_per_task: int = 1  # numSamples (N)
    temperature: float = 0.2
    top_p: float = 0.95
    sorting_method: str = "generation_order"  # generation_order | logprob | random
    
    # Compile Rate definition
    compile_rate_definition: str = "percentage of samples that run without SyntaxError during exec"
    
    # Timeout and edge case handling
    timeout_handling: str = "counted as failure (TLE)"
    memory_limit_handling: str = "counted as failure (MLE)"


@dataclass
class CodeQualityMetrics:
    """Code quality metrics - displayed in main report"""
    avg_code_length: float = 0.0
    avg_line_count: float = 0.0
    extra_io_rate: float = 0.0  # Percentage containing print/input
    interface_compliance_rate: float = 0.0  # Percentage containing function definition


@dataclass
class ReproducibilityInfo:
    """Reproducibility information"""
    python_seed: Optional[int] = None
    numpy_seed: Optional[int] = None
    torch_seed: Optional[int] = None
    evaluator_version: str = "1.0.0"
    checkpoint_hash: Optional[str] = None  # First 8 chars of model file MD5


@dataclass
class EvalSummary:
    """Complete evaluation log"""
    # Metadata
    eval_run_id: str
    eval_time: str
    seed: int
    git_commit: Optional[str]
    
    # Model information
    base_model_name: str
    checkpoint_path: str
    checkpoint_step: Optional[int] = None
    checkpoint_epoch: Optional[int] = None
    
    # Configuration
    environment: Optional[EvalEnvironmentInfo] = None
    generation_config: Optional[GenerationSettings] = None
    judge_config: Optional[JudgeSettings] = None
    dataset_info: Optional[DatasetInfo] = None
    
    # P1: Evaluation methodology configuration
    evaluation_protocol: Optional[EvaluationProtocol] = None
    
    # P1: Reproducibility information
    reproducibility_info: Optional[ReproducibilityInfo] = None
    
    # Metrics
    metrics_overall: Optional[MetricsOverall] = None
    error_distribution: Optional[ErrorDistribution] = None
    time_stats: Optional[TimeStats] = None
    segment_breakdown: Optional[SegmentBreakdown] = None
    
    # P1: Per-problem pass rate distribution
    per_problem_stats: Optional[PerProblemStats] = None
    
    # P0: Representative failure cases grouped by error type
    failure_examples_by_type: Optional[FailureExamplesByType] = None
    
    # P2: Code quality metrics
    code_quality: Optional[CodeQualityMetrics] = None
    
    # Post-processing
    postprocess_stats: Optional[PostProcessStats] = None
    
    # Sample results (only save failures + typical cases)
    sample_results: List[SampleResult] = field(default_factory=list)
    
    # Artifact paths
    artifact_paths: Dict[str, str] = field(default_factory=dict)


# ============================================================================
# Eval Logger Class
# ============================================================================

class EvalLogger:
    """Evaluation log collector"""
    
    @staticmethod
    def collect_environment() -> EvalEnvironmentInfo:
        """Collect evaluation environment information"""
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
        """Get current Git commit hash"""
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
        """Calculate dataset file hash"""
        try:
            if os.path.isfile(dataset_path):
                with open(dataset_path, 'rb') as f:
                    return hashlib.md5(f.read()).hexdigest()[:8]
        except:
            pass
        return None
    
    @staticmethod
    def generate_eval_run_id() -> str:
        """Generate evaluation run ID"""
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
        """Create new evaluation log"""
        if eval_run_id is None:
            eval_run_id = self.generate_eval_run_id()
        
        # Set default judge configuration
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
        """Set dataset information"""
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
        """Add sample-level result"""
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
        """Set overall metrics"""
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
        """Set error distribution"""
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
        """Set time statistics"""
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
        """Set post-processing statistics"""
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
        """P1: Set evaluation methodology configuration"""
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
        """P1: Set reproducibility information"""
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
        """P2: Set code quality metrics"""
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
        """P1: Set segment statistics"""
        log.segment_breakdown = SegmentBreakdown(
            by_difficulty=by_difficulty,
            by_category=by_category,
        )
    
    def set_per_problem_stats(
        self,
        log: EvalSummary,
        pass_rates: List[float],
    ) -> None:
        """P1: Set per-problem pass rate distribution statistics"""
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
        P0: Set representative failure cases grouped by error type
        
        Diverse sampling strategy:
        1. Prioritize samples from different task_ids (avoid same problem repetition)
        2. If all errors of the same type come from the same problem, select different sample_indices
        3. Random shuffle to avoid always selecting the first samples
        """
        import random
        
        # Group failure samples by error type
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
            
            # Map error type to category
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
        
        # Diverse sampling
        result = FailureExamplesByType()
        
        for category, samples in failures_by_type.items():
            if not samples:
                continue
            
            # Random shuffle to avoid always selecting same samples
            random.shuffle(samples)
            
            # Group by task_id, prioritize samples from different problems
            task_groups: Dict[str, List[SampleResult]] = {}
            for s in samples:
                if s.task_id not in task_groups:
                    task_groups[s.task_id] = []
                task_groups[s.task_id].append(s)
            
            # Round-robin selection (ensure diversity)
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
                        prompt_preview=sample.prompt,  # Save complete, no truncation
                        output_preview=sample.raw_output,  # Save complete, no truncation
                        traceback_preview=sample.traceback or '',  # Save complete, no truncation
                        error_type=sample.error_type or '',
                        verdict=sample.verdict,
                    ))
                    # If no more samples for this task_id, remove it
                    if not task_groups[task_id]:
                        task_ids.remove(task_id)
                idx += 1
                if idx > len(samples):  # Prevent infinite loop
                    break
            
            # Set to result
            setattr(result, category, selected)
        
        log.failure_examples_by_type = result
    
    def finalize(self, log: EvalSummary) -> EvalSummary:
        """Finalize evaluation log"""
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
        """Save log to JSON file"""
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(asdict(log), f, indent=2, ensure_ascii=False)
        
        logger.info(f"Eval summary saved to: {output_path}")
    
    def to_json(self, log: EvalSummary) -> str:
        """Convert to JSON string"""
        return json.dumps(asdict(log), ensure_ascii=False)
    
    def to_dict(self, log: EvalSummary) -> dict:
        """Convert to dictionary"""
        return asdict(log)


# ============================================================================
# Convenience Functions
# ============================================================================

def create_eval_log(**kwargs) -> EvalSummary:
    """Convenience function to quickly create evaluation log"""
    return EvalLogger().create_eval_log(**kwargs)


def output_eval_log_event(log: EvalSummary):
    """Output evaluation log event to stdout for backend parsing"""
    print(json.dumps({
        "type": "eval_log",
        "data": asdict(log)
    }))


if __name__ == "__main__":
    # Test code
    logging.basicConfig(level=logging.INFO)
    
    eval_logger = EvalLogger()
    log = eval_logger.create_eval_log(
        seed=42,
        base_model_name="Qwen/Qwen2.5-Coder-1.5B",
        checkpoint_path="/path/to/checkpoint",
    )
    
    # Set dataset
    eval_logger.set_dataset_info(
        log,
        dataset_path="./data/test.jsonl",
        dataset_name="CodeEval-Test",
        split="test",
        total_problems=164,
        total_samples=1640,
    )
    
    # Set metrics
    eval_logger.set_metrics(
        log,
        pass_at_1=45.2,
        pass_at_5=62.1,
        pass_at_10=71.3,
        compile_rate=85.4,
        total_problems=164,
        total_samples=1640,
    )
    
    # Set error distribution
    eval_logger.set_error_distribution(
        log,
        syntax_error_rate=5.2,
        runtime_error_rate=12.3,
        timeout_rate=2.1,
        wrong_answer_rate=35.2,
    )
    
    # Set post-processing statistics
    eval_logger.set_postprocess_stats(
        log,
        enabled=True,
        total_attempts=500,
        successful_fixes=120,
        pass_at_1_before=42.1,
        pass_at_1_after=45.2,
    )
    
    # Finalize
    eval_logger.finalize(log)
    
    print("\n--- JSON Output ---")
    print(eval_logger.to_json(log))
