#!/usr/bin/env python3
"""
Report Generator - Extremely detailed and comprehensive training report generator

This script can run standalone to generate complete HTML reports from training logs,
configuration files, and evaluation results.

Reports include:
- Experiment metadata (time, seed, Git version)
- Complete environment version info
- Hardware configuration details
- Dataset statistics
- Model architecture info
- Training hyperparameters (complete list)
- LoRA configuration details
- Training curves (Loss, Learning Rate)
- All checkpoint information
- Evaluation results (Pass@k, error distribution, execution time)
- Complete raw configuration JSON

Usage:
    python3 report_generator.py --run-dir <run_directory> --output <output.html>
    python3 report_generator.py --config <config.json> --metrics <metrics.json> --output <output.html>
"""

import argparse
import json
import os
import sys
import html
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import platform
import math


def load_json_file(path: str) -> Dict[str, Any]:
    """Load a JSON file"""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: Failed to load {path}: {e}")
        return {}


def format_number(num: Optional[float]) -> str:
    """Format large numbers to readable form"""
    if num is None:
        return "N/A"
    # Handle string type input
    if isinstance(num, str):
        try:
            num = float(num)
        except (ValueError, TypeError):
            return str(num)  # Return original string if cannot convert
    if num >= 1_000_000_000:
        return f"{num / 1_000_000_000:.2f}B"
    elif num >= 1_000_000:
        return f"{num / 1_000_000:.2f}M"
    elif num >= 1_000:
        return f"{num / 1_000:.1f}K"
    return str(int(num)) if num == int(num) else f"{num:.2f}"


def format_duration(seconds: Optional[float]) -> str:
    """Format duration"""
    if seconds is None:
        return "N/A"
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def get_value(data: Dict, *keys, default=None):
    """Safely get nested dictionary value"""
    for key in keys:
        if isinstance(data, dict) and key in data:
            data = data[key]
        else:
            return default
    return data if data is not None else default


def uniform_sample_indices(total_count: int, losses: List[float] = None, max_samples: int = 50) -> List[int]:
    """
    Unified sampling function - uniformly sample from all data points
    
    Strategy:
    1. If data count <= max_samples, return all indices
    2. Otherwise use equal-spaced sampling (linspace style), ensuring first and last are included
    3. Additionally include the lowest loss point (if losses are provided)
    
    Args:
        total_count: Total number of data points
        losses: List of loss values (optional, used to find lowest point)
        max_samples: Maximum number of samples
    
    Returns:
        Sorted list of sample indices
    """
    if total_count == 0:
        return []
    
    if total_count == 1:
        return [0]
    
    # If data count less than or equal to max_samples, return all indices
    if total_count <= max_samples:
        return list(range(total_count))
    
    # Use equal-spaced sampling (linspace style)
    # Reserve 1 position for lowest loss point (if needed), distribute rest evenly
    effective_samples = max_samples - 1 if losses else max_samples
    
    sample_indices = set()
    
    # Equal-spaced sampling: 0, step, 2*step, ..., total_count-1
    for i in range(effective_samples):
        # Calculate index: i * (total_count - 1) / (effective_samples - 1)
        # This ensures first is 0, last is total_count - 1
        idx = round(i * (total_count - 1) / (effective_samples - 1))
        sample_indices.add(idx)
    
    # Add lowest loss point
    if losses and len(losses) == total_count:
        min_loss = min(losses)
        min_loss_idx = losses.index(min_loss)
        sample_indices.add(min_loss_idx)
    
    # Sort and return
    return sorted(sample_indices)


# ============================================================================
# Data Validator - P0 Data Consistency Checks
# ============================================================================

class DataValidator:
    """Data Validator - Detect inconsistencies in report data"""
    
    def __init__(self):
        self.warnings: List[str] = []
        self.errors: List[str] = []
    
    def validate_dataset_stats(self, dataset_config: Dict[str, Any]) -> None:
        """Validate dataset statistics consistency"""
        total_samples = dataset_config.get("samples", 0) or 0
        train_samples = dataset_config.get("train_samples", 0) or 0
        val_samples = dataset_config.get("val_samples", 0) or 0
        test_samples = dataset_config.get("test_samples", 0) or 0
        
        # Check total_samples < train_samples
        if total_samples < train_samples:
            self.warnings.append(
                f"Dataset stats mismatch: total_samples({total_samples}) < train_samples({train_samples})"
            )
        
        # Check if sum of subsets is reasonable
        subset_sum = train_samples + val_samples + test_samples
        if total_samples > 0 and subset_sum > 0 and subset_sum > total_samples * 1.1:
            self.warnings.append(
                f"Dataset split mismatch: train+val+test({subset_sum}) > total({total_samples})"
            )
    
    def validate_steps(self, planned_steps: Optional[int], actual_steps: Optional[int], 
                       metrics_count: int) -> None:
        """Validate step count consistency - no longer generates warnings, step info is shown in report"""
        # Step differences are shown in Key Metrics (Planned/Logged/Effective Steps), no warning needed
        pass
    
    def validate_learning_rate(self, config_lr: Optional[str], 
                                initial_lr_from_metrics: Optional[float]) -> None:
        """Validate learning rate config consistency - no longer generates warnings, LR info is shown in report"""
        # LR differences are shown in Training Configuration (Config LR vs Actual Initial LR), no warning needed
        pass
    
    def validate_scheduler(self, scheduler_config: str, lr_values: List[float]) -> str:
        """Detect actual scheduler type used"""
        if len(lr_values) < 3:
            return scheduler_config
        
        # Analyze LR change pattern
        # Linear: equal-difference decreasing
        # Cosine: fast first then slow
        # Constant: unchanged
        diffs = [lr_values[i+1] - lr_values[i] for i in range(len(lr_values)-1)]
        
        if all(abs(d) < 1e-10 for d in diffs):
            detected = "constant"
        elif len(diffs) >= 2:
            # Check if close to arithmetic progression
            avg_diff = sum(diffs) / len(diffs)
            variance = sum((d - avg_diff) ** 2 for d in diffs) / len(diffs)
            if variance < 1e-12:  # Very small variance = linear
                detected = "linear"
            else:
                detected = "cosine"  # Assume other cases are cosine
        else:
            detected = scheduler_config
        
        if detected != scheduler_config.lower():
            self.warnings.append(
                f"Scheduler mismatch: config={scheduler_config}, detected={detected}"
            )
        
        return detected
    
    def get_all_warnings(self) -> List[str]:
        """Get all warnings"""
        return self.warnings
    
    def get_all_errors(self) -> List[str]:
        """Get all errors"""
        return self.errors
    
    def has_issues(self) -> bool:
        """Check if there are any issues"""
        return len(self.warnings) > 0 or len(self.errors) > 0


def deduplicate_metrics(metrics: List[Dict[str, Any]], filter_no_lr: bool = True) -> List[Dict[str, Any]]:
    """
    Deduplicate metrics by global_step, keeping the last record for each step.
    P0-4: Filter out invalid records (loss is null/0).
    P0-FIX: If filter_no_lr=True, filter out abnormal steps without lr.
    """
    if not metrics:
        return []
    
    # Group by step, keep the last one
    step_to_metric = {}
    for m in metrics:
        step = m.get("step")
        if step is not None:
            loss = m.get("loss")
            lr = m.get("lr") or m.get("learning_rate")
            
            # Must have valid loss
            if loss is None or loss <= 0:
                continue
            
            # P0-FIX: If filter is set, skip warmup steps without lr or lr=0
            # lr=0 means no real parameter update yet (during gradient accumulation)
            if filter_no_lr and (lr is None or lr <= 0):
                continue
                
            step_to_metric[step] = m
    
    # Sort by step and return
    return [step_to_metric[s] for s in sorted(step_to_metric.keys())]


def extract_lr_values(metrics: List[Dict[str, Any]]) -> List[float]:
    """Extract learning rate values from metrics"""
    lr_values = []
    for m in metrics:
        lr = m.get("lr") or m.get("learning_rate")
        if lr is not None:
            try:
                lr_values.append(float(lr))
            except (ValueError, TypeError):
                pass
    return lr_values


def get_valid_final_loss(metrics: List[Dict[str, Any]]) -> Optional[float]:
    """
    P0-FIX: Get valid final loss (last step with lr)
    Exclude epoch average loss that may appear after training ends
    """
    if not metrics:
        return None
    
    # Search backwards for step with lr
    for m in reversed(metrics):
        loss = m.get("loss")
        lr = m.get("lr") or m.get("learning_rate")
        if loss is not None and loss > 0 and lr is not None:
            return loss
    
    # If no step with lr found, use second to last
    if len(metrics) >= 2:
        loss = metrics[-2].get("loss")
        if loss is not None and loss > 0:
            return loss
    
    # Last fallback
    return metrics[-1].get("loss") if metrics else None


class ReportGenerator:
    """Extremely detailed and comprehensive report generator"""
    
    def __init__(self):
        self.config: Dict[str, Any] = {}
        self.metrics: List[Dict[str, Any]] = []
        self.eval_result: Dict[str, Any] = {}
        self.experiment_meta: Dict[str, Any] = {}
        self.lora_stats: Dict[str, Any] = {}
        self.checkpoints: List[Dict[str, Any]] = []
        self.run_info: Dict[str, Any] = {}
        self.data_quality_stats: Dict[str, Any] = {}  # P2: Data quality analysis
        
    def load_from_directory(self, run_dir: str):
        """Load all data from run directory"""
        run_path = Path(run_dir)
        
        # Load configuration
        config_path = run_path / "config.json"
        if config_path.exists():
            self.config = load_json_file(str(config_path))
            
        # Load training metrics
        metrics_path = run_path / "metrics.json"
        if metrics_path.exists():
            data = load_json_file(str(metrics_path))
            self.metrics = data if isinstance(data, list) else data.get("metrics", [])
            
        # Load evaluation results
        eval_path = run_path / "eval_result.json"
        if eval_path.exists():
            self.eval_result = load_json_file(str(eval_path))
            
        # Load experiment metadata
        meta_path = run_path / "experiment_meta.json"
        if meta_path.exists():
            self.experiment_meta = load_json_file(str(meta_path))
            
        # Load LoRA statistics
        lora_path = run_path / "lora_stats.json"
        if lora_path.exists():
            self.lora_stats = load_json_file(str(lora_path))
            
        # Load checkpoint information
        checkpoints_path = run_path / "checkpoints.json"
        if checkpoints_path.exists():
            data = load_json_file(str(checkpoints_path))
            self.checkpoints = data if isinstance(data, list) else data.get("checkpoints", [])
            
        # Load run information
        info_path = run_path / "run_info.json"
        if info_path.exists():
            self.run_info = load_json_file(str(info_path))
            
        # Load data quality statistics (P2: Data Quality Analysis)
        quality_stats_path = run_path / "data_quality_stats.json"
        if quality_stats_path.exists():
            self.data_quality_stats = load_json_file(str(quality_stats_path))
            
    def load_from_files(self, config_path: Optional[str] = None, 
                        metrics_path: Optional[str] = None,
                        eval_path: Optional[str] = None,
                        meta_path: Optional[str] = None):
        """Load data from individual files"""
        if config_path and os.path.exists(config_path):
            self.config = load_json_file(config_path)
        if metrics_path and os.path.exists(metrics_path):
            data = load_json_file(metrics_path)
            self.metrics = data if isinstance(data, list) else data.get("metrics", [])
        if eval_path and os.path.exists(eval_path):
            self.eval_result = load_json_file(eval_path)
        if meta_path and os.path.exists(meta_path):
            self.experiment_meta = load_json_file(meta_path)
            
    def collect_system_info(self) -> Dict[str, Any]:
        """Collect current system info (if metadata not provided)"""
        info = {
            "os": platform.platform(),
            "python": platform.python_version(),
        }
        
        try:
            import torch
            info["pytorch"] = torch.__version__
            if torch.cuda.is_available():
                info["cuda"] = torch.version.cuda
                info["gpu"] = torch.cuda.get_device_name(0)
                info["gpu_memory"] = f"{torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB"
        except ImportError:
            pass
            
        try:
            import transformers
            info["transformers"] = transformers.__version__
        except ImportError:
            pass
            
        try:
            import peft
            info["peft"] = peft.__version__
        except ImportError:
            pass
            
        try:
            import trl
            info["trl"] = trl.__version__
        except ImportError:
            pass
            
        return info
    
    def generate_markdown(self, title: Optional[str] = None) -> str:
        """Generate extremely detailed and comprehensive Markdown report"""
        
        # =====================================================================
        # P0: Data preprocessing - deduplicate and filter invalid metrics (consistent with HTML)
        # =====================================================================
        deduplicated_metrics = deduplicate_metrics(self.metrics)
        
        # Extract data from each section
        training_config = self.config.get("training", {})
        lora_config = self.config.get("lora", {})
        model_config = self.config.get("model", {})
        dataset_config = self.config.get("dataset", {})
        
        # =====================================================================
        # P0: Detect run type - distinguish training and evaluation reports
        # =====================================================================
        run_type = self.run_info.get("type", self.config.get("run_type", ""))
        is_eval_run = run_type == "eval" or self.config.get("evaluator") is not None
        
        # Evaluation-specific configuration
        eval_protocol = self.config.get("eval_protocol", {})
        code_quality = self.eval_result.get("codeQuality", self.eval_result.get("code_quality", {}))
        reproducibility = self.config.get("reproducibility", {})
        
        # P0: Fix dataset stats for evaluation reports - use real data from eval_result
        if is_eval_run:
            eval_total_problems = (self.eval_result.get("totalProblems") or 
                                   self.eval_result.get("total_problems") or 0)
            eval_total_samples = (self.eval_result.get("totalSamples") or 
                                  self.eval_result.get("total_samples") or 0)
            if eval_total_problems > 0:
                dataset_config["samples"] = eval_total_problems
                dataset_config["eval_problems"] = eval_total_problems
                dataset_config["eval_samples"] = eval_total_samples
        
        # System info (empty dict also treated as no data)
        system_info = self.experiment_meta if self.experiment_meta else self.collect_system_info()
        
        # Run information
        run_name = title or self.run_info.get("name", self.config.get("run_name", "Training Run"))
        run_id = self.run_info.get("id", "N/A")
        duration = self.run_info.get("duration", "")
        seed = self.config.get("seed", training_config.get("seed", "N/A"))
        git_commit = self.run_info.get("git_commit", "N/A")
        
        # =====================================================================
        # Training steps statistics - distinguish three different concepts of steps
        # =====================================================================
        # 1. Planned steps: steps planned in configuration
        planned_steps = training_config.get("total_steps") or training_config.get("planned_steps")
        
        # 2. Raw logged steps: total steps recorded in raw logs (including warmup/pre-log)
        # Prioritize value passed from Node.js
        raw_logged_steps_from_config = training_config.get("raw_logged_steps")
        raw_logged_steps = raw_logged_steps_from_config if raw_logged_steps_from_config else (len(self.metrics) if self.metrics else 0)
        
        # 3. Effective update steps: steps where parameter updates actually occurred
        # Use actual length of deduplicated_metrics filtered by Python (most accurate)
        effective_steps = len(deduplicated_metrics) if deduplicated_metrics else 0
        
        # total_steps for display (prefer effective_steps)
        total_steps = effective_steps if effective_steps > 0 else (planned_steps or "N/A")
        
        # P0-FIX: Get valid final_loss (last step with lr)
        final_loss = get_valid_final_loss(deduplicated_metrics) if deduplicated_metrics else None
        
        # Calculate warmup steps (raw logged - effective steps)
        warmup_steps = raw_logged_steps - effective_steps if raw_logged_steps > effective_steps else 0
        
        # Get first and last effective step numbers (for Note display)
        first_effective_step = deduplicated_metrics[0].get("step", 1) if deduplicated_metrics else 1
        last_effective_step = deduplicated_metrics[-1].get("step", effective_steps) if deduplicated_metrics else effective_steps
        
        # LoRA statistics
        lora_stats = self.lora_stats or {}
        trainable_params = lora_stats.get("trainable_params")
        total_params = lora_stats.get("total_params")
        trainable_percent = lora_stats.get("trainable_percent")
        
        # Evaluation results
        eval_result = self.eval_result or {}
        pass_at_1 = eval_result.get("pass_at_1") or eval_result.get("passAt1")
        pass_at_5 = get_value(eval_result, "pass_at_k", "5") or get_value(eval_result, "passAtK", "5")
        pass_at_10 = get_value(eval_result, "pass_at_k", "10") or get_value(eval_result, "passAtK", "10")
        compile_rate = eval_result.get("compile_rate") or eval_result.get("compileRate")
        
        error_stats = eval_result.get("error_stats", eval_result.get("errorStats", {}))
        time_stats = eval_result.get("time_stats", eval_result.get("timeStats", {}))
        
        # Formatting function
        def fmt(val, suffix="", decimals=2):
            if val is None:
                return "N/A"
            try:
                return f"{float(val):.{decimals}f}{suffix}"
            except:
                return str(val)
        
        def fmt_na(val):
            return str(val) if val is not None else "N/A"
        
        # Generate Markdown
        md_lines = []
        
        # Title
        md_lines.append(f"# {run_name}")
        md_lines.append("")
        # P0: Distinguish report type title
        report_type_label = "Evaluation Report" if is_eval_run else "Training Report"
        md_lines.append(f"> {report_type_label} | Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        md_lines.append("")
        
        # Overview
        md_lines.append("## Overview")
        md_lines.append("")
        md_lines.append(f"| Property | Value |")
        md_lines.append(f"|----------|-------|")
        md_lines.append(f"| Run ID | `{run_id}` |")
        md_lines.append(f"| Duration | {duration or 'N/A'} |")
        md_lines.append(f"| Seed | {seed} |")
        if git_commit and git_commit != "N/A":
            md_lines.append(f"| Git Commit | `{git_commit[:7] if len(git_commit) > 7 else git_commit}` |")
        md_lines.append("")
        
        # Key metrics
        md_lines.append("## Key Metrics")
        md_lines.append("")
        md_lines.append("| Metric | Value |")
        md_lines.append("|--------|-------|")
        md_lines.append(f"| **Pass@1** | {fmt(pass_at_1, '%')} |")
        md_lines.append(f"| Compile Rate | {fmt(compile_rate, '%')} |")
        
        # P0: Evaluation reports don't show training-related metrics
        if not is_eval_run:
            md_lines.append(f"| Final Loss | {fmt(final_loss, '', 4) if final_loss else 'N/A'} |")
            
            # Show three types of steps (if there are differences)
            if planned_steps and (raw_logged_steps != effective_steps or planned_steps != effective_steps):
                if planned_steps:
                    md_lines.append(f"| Planned Steps | {planned_steps} |")
                if raw_logged_steps != effective_steps:
                    md_lines.append(f"| Logged Steps | {raw_logged_steps} |")
                md_lines.append(f"| **Effective Update Steps** | **{effective_steps}** |")
            else:
                md_lines.append(f"| Total Steps | {total_steps} |")
            
            md_lines.append(f"| Trainable Params | {format_number(trainable_params)} |")
            md_lines.append(f"| Trainable % | {fmt(trainable_percent, '%', 4) if trainable_percent else 'N/A'} |")
        else:
            # P0: Evaluation reports show evaluation-related statistics
            eval_total_problems = dataset_config.get('eval_problems', 0)
            eval_total_samples = dataset_config.get('eval_samples', 0)
            md_lines.append(f"| Total Problems (N_tasks) | {eval_total_problems} |")
            md_lines.append(f"| Total Samples (N x k) | {eval_total_samples} |")
            if eval_total_problems < 30:
                md_lines.append(f"| Sample Size Warning | N_tasks={eval_total_problems} is small |")
        md_lines.append("")
        
        # P0: Add step difference explanation (training reports only, not shown in eval reports)
        if not is_eval_run and warmup_steps > 0:
            md_lines.append(f"> **Note:** Steps 1-{first_effective_step - 1} are pre-update logs during warmup/gradient accumulation (lr=0). Effective parameter updates: {effective_steps} steps (Steps {first_effective_step}-{last_effective_step}).")
            md_lines.append("")
        
        # Model information
        md_lines.append("## Model")
        md_lines.append("")
        md_lines.append("| Property | Value |")
        md_lines.append("|----------|-------|")
        md_lines.append(f"| Model Name | {fmt_na(model_config.get('name', self.config.get('model_name')))} |")
        md_lines.append(f"| Model Path | {fmt_na(model_config.get('path', self.config.get('model_path')))} |")
        md_lines.append(f"| Parameters | {fmt_na(model_config.get('params'))} |")
        md_lines.append(f"| Quantization | {fmt_na(lora_config.get('quantization', 'None'))} |")
        md_lines.append("")
        
        # Dataset information
        md_lines.append("## Dataset")
        md_lines.append("")
        md_lines.append("| Property | Value |")
        md_lines.append("|----------|-------|")
        md_lines.append(f"| Dataset Name | {fmt_na(dataset_config.get('name', self.config.get('dataset_name')))} |")
        md_lines.append(f"| Dataset Path | {fmt_na(dataset_config.get('path', self.config.get('dataset_path')))} |")
        md_lines.append(f"| Total Samples | {fmt_na(dataset_config.get('samples'))} |")
        md_lines.append(f"| Train Samples | {fmt_na(dataset_config.get('train_samples'))} |")
        md_lines.append(f"| Total Tokens | {format_number(dataset_config.get('total_tokens'))} |")
        md_lines.append("")
        
        # =====================================================================
        # P2: Data Quality Statistics (from analyze_data_quality.py)
        # =====================================================================
        if self.data_quality_stats:
            dq = self.data_quality_stats
            
            md_lines.append("## Dataset Quality Analysis")
            md_lines.append("")
            md_lines.append(f"> Quality Score: **{fmt(dq.get('quality_score'), '/100', 1)}**")
            md_lines.append("")
            
            # Token Length Distribution
            train_token_stats = dq.get("train_token_stats", {})
            eval_token_stats = dq.get("eval_token_stats", {})
            
            if train_token_stats:
                md_lines.append("### Token Length Distribution")
                md_lines.append("")
                md_lines.append("| Statistic | Training Set | Eval Set |")
                md_lines.append("|-----------|-------------|----------|")
                md_lines.append(f"| Mean | {fmt(train_token_stats.get('mean'), '', 1)} | {fmt(eval_token_stats.get('mean'), '', 1) if eval_token_stats else 'N/A'} |")
                md_lines.append(f"| Median (P50) | {fmt_na(train_token_stats.get('median'))} | {fmt_na(eval_token_stats.get('median')) if eval_token_stats else 'N/A'} |")
                md_lines.append(f"| P95 | {fmt_na(train_token_stats.get('p95'))} | {fmt_na(eval_token_stats.get('p95')) if eval_token_stats else 'N/A'} |")
                md_lines.append(f"| Max | {fmt_na(train_token_stats.get('max_length'))} | {fmt_na(eval_token_stats.get('max_length')) if eval_token_stats else 'N/A'} |")
                md_lines.append("")
            
            # Truncation & Quality
            train_trunc = dq.get("train_truncation", {})
            eval_trunc = dq.get("eval_truncation", {})
            
            if train_trunc:
                md_lines.append("### Truncation & Data Quality")
                md_lines.append("")
                md_lines.append("| Metric | Training Set | Eval Set |")
                md_lines.append("|--------|-------------|----------|")
                md_lines.append(f"| Max Seq Length | {fmt_na(train_trunc.get('max_seq_length'))} | {fmt_na(eval_trunc.get('max_seq_length')) if eval_trunc else 'N/A'} |")
                md_lines.append(f"| Truncation Rate | {fmt(train_trunc.get('truncated_rate'), '%', 2)} | {fmt(eval_trunc.get('truncated_rate'), '%', 2) if eval_trunc else 'N/A'} |")
                md_lines.append(f"| Empty Samples | {fmt_na(train_trunc.get('empty_count'))} | {fmt_na(eval_trunc.get('empty_count')) if eval_trunc else 'N/A'} |")
                md_lines.append(f"| Short Samples (<10 tok) | {fmt_na(train_trunc.get('short_count'))} ({fmt(train_trunc.get('short_rate'), '%', 2)}) | {fmt_na(eval_trunc.get('short_count')) if eval_trunc else 'N/A'} |")
                md_lines.append("")
            
            # Leakage Check
            leakage = dq.get("leakage_check", {})
            if leakage:
                md_lines.append("### Train-Eval Leakage Check")
                md_lines.append("")
                md_lines.append("| Detection Method | Count | Rate |")
                md_lines.append("|-----------------|-------|------|")
                md_lines.append(f"| Exact Match | {fmt_na(leakage.get('exact_match_count'))} | {fmt(leakage.get('exact_match_rate'), '%', 2)} |")
                md_lines.append(f"| Normalized Match | {fmt_na(leakage.get('normalized_match_count'))} | {fmt(leakage.get('normalized_match_rate'), '%', 2)} |")
                threshold = leakage.get('similarity_threshold', 0.8)
                md_lines.append(f"| High Similarity (>{threshold}) | {fmt_na(leakage.get('high_similarity_count'))} | {fmt(leakage.get('high_similarity_rate'), '%', 2)} |")
                md_lines.append("")
                
                # Leakage assessment
                exact_rate = leakage.get('exact_match_rate', 0) or 0
                high_sim_rate = leakage.get('high_similarity_rate', 0) or 0
                if exact_rate < 1 and high_sim_rate < 5:
                    md_lines.append("> ✅ **Leakage Assessment: Clean** - No significant train-eval leakage detected.")
                elif exact_rate < 5 and high_sim_rate < 10:
                    md_lines.append(f"> ⚠️ **Leakage Assessment: Minor** - {exact_rate:.1f}% exact, {high_sim_rate:.1f}% high similarity.")
                else:
                    md_lines.append(f"> ❌ **Leakage Assessment: Significant** - {exact_rate:.1f}% exact, {high_sim_rate:.1f}% high similarity. Consider re-splitting data.")
                md_lines.append("")
        
        # P0: Training configuration (training reports only, skip for eval reports)
        if not is_eval_run:
            md_lines.append("## Training Configuration")
            md_lines.append("")
            md_lines.append("| Parameter | Value |")
            md_lines.append("|-----------|-------|")
            md_lines.append(f"| Batch Size | {training_config.get('batchSize', training_config.get('batch_size', 'N/A'))} |")
            md_lines.append(f"| Gradient Accumulation | {training_config.get('gradientAccumulation', training_config.get('gradAccum', 'N/A'))} |")
            batch_size = training_config.get('batchSize', 1)
            grad_accum = training_config.get('gradientAccumulation', training_config.get('gradAccum', 8))
            md_lines.append(f"| **Effective Batch Size** | {batch_size * grad_accum} |")
            # P0-FIX: Distinguish Config LR vs Actual Initial LR
            config_lr = training_config.get('lr', training_config.get('learning_rate', 'N/A'))
            # Get actual initial LR from first step of metrics
            actual_init_lr = None
            if self.metrics and len(self.metrics) > 0:
                first_metric = self.metrics[0]
                actual_init_lr = first_metric.get('lr') or first_metric.get('learning_rate')
            
            md_lines.append(f"| Config Learning Rate | {config_lr} |")
            if actual_init_lr and str(config_lr) != str(actual_init_lr):
                md_lines.append(f"| Actual Initial LR | {actual_init_lr:.2e} |")
            md_lines.append(f"| LR Scheduler | {training_config.get('scheduler', 'N/A')} |")
            md_lines.append(f"| Warmup Ratio | {training_config.get('warmupRatio', 'N/A')} |")
            md_lines.append(f"| Epochs | {training_config.get('epochs', 'N/A')} |")
            md_lines.append(f"| Max Sequence Length | {training_config.get('maxSeqLen', training_config.get('maxLength', 'N/A'))} |")
            md_lines.append(f"| Optimizer | {training_config.get('optimizer', 'N/A')} |")
            md_lines.append(f"| Weight Decay | {training_config.get('weightDecay', 'N/A')} |")
            md_lines.append(f"| Precision | {training_config.get('precision', 'N/A')} |")
            md_lines.append("")
            
            # LoRA configuration
            if lora_config.get("enabled", True):
                md_lines.append("## LoRA Configuration")
                md_lines.append("")
                md_lines.append("| Parameter | Value |")
                md_lines.append("|-----------|-------|")
                md_lines.append(f"| Enabled | {'Yes' if lora_config.get('enabled', True) else 'No'} |")
                md_lines.append(f"| Rank (r) | {fmt_na(lora_config.get('rank', lora_config.get('r')))} |")
                md_lines.append(f"| Alpha | {fmt_na(lora_config.get('alpha', lora_config.get('lora_alpha')))} |")
                md_lines.append(f"| Dropout | {fmt_na(lora_config.get('dropout', lora_config.get('lora_dropout')))} |")
                target_modules = lora_config.get("targetModules", lora_config.get("target_modules", []))
                md_lines.append(f"| Target Modules | {', '.join(target_modules) if target_modules else 'N/A'} |")
                md_lines.append(f"| Quantization | {fmt_na(lora_config.get('quantization'))} |")
                md_lines.append(f"| Trainable Parameters | {format_number(trainable_params)} |")
                md_lines.append(f"| Total Parameters | {format_number(total_params)} |")
                md_lines.append(f"| Trainable Percentage | {fmt(trainable_percent, '%', 4) if trainable_percent else 'N/A'} |")
                md_lines.append("")
        
        # =====================================================================
        # P1: Evaluation Protocol (eval reports only)
        # =====================================================================
        if is_eval_run:
            md_lines.append("## Evaluation Protocol")
            md_lines.append("")
            md_lines.append("> **Important**: This section defines how metrics are computed for reproducibility.")
            md_lines.append("")
            md_lines.append("| Parameter | Value |")
            md_lines.append("|-----------|-------|")
            
            num_samples = self.config.get("numSamples", eval_protocol.get("samples_per_task", "N/A"))
            temperature = self.config.get("temperature", eval_protocol.get("temperature", 0.2))
            top_p = self.config.get("topP", eval_protocol.get("top_p", 0.95))
            timeout = self.config.get("timeout", 10)
            
            md_lines.append(f"| Pass@k Definition | Success if any of the first k samples passes all tests |")
            md_lines.append(f"| Samples per Task (N) | {num_samples} |")
            md_lines.append(f"| Temperature | {temperature} |")
            md_lines.append(f"| Top-p | {top_p} |")
            md_lines.append(f"| Sorting Method | Generation order (first-to-last) |")
            md_lines.append(f"| Compile Rate Def. | % of samples without SyntaxError during exec |")
            md_lines.append(f"| Timeout Handling | Counted as failure (TLE) after {timeout}s |")
            md_lines.append("")
            
            # Reproducibility information
            md_lines.append("### Reproducibility")
            md_lines.append("")
            md_lines.append("| Parameter | Value |")
            md_lines.append("|-----------|-------|")
            md_lines.append(f"| Seed | {seed} |")
            md_lines.append(f"| Git Commit | {git_commit if git_commit != 'N/A' else 'Not recorded'} |")
            md_lines.append(f"| Evaluator Version | {reproducibility.get('evaluator_version', '1.0.0')} |")
            md_lines.append("")
        
        # Evaluation results
        md_lines.append("## Evaluation Results")
        md_lines.append("")
        md_lines.append("### Pass@k Metrics")
        md_lines.append("")
        md_lines.append("| Metric | Value |")
        md_lines.append("|--------|-------|")
        md_lines.append(f"| **Pass@1** | {fmt(pass_at_1, '%')} |")
        md_lines.append(f"| Pass@5 | {fmt(pass_at_5, '%')} |")
        md_lines.append(f"| Pass@10 | {fmt(pass_at_10, '%')} |")
        md_lines.append(f"| Compile Rate | {fmt(compile_rate, '%')} |")
        md_lines.append("")
        
        md_lines.append("### Error Distribution")
        md_lines.append("")
        md_lines.append("| Error Type | Rate |")
        md_lines.append("|------------|------|")
        md_lines.append(f"| Syntax Error | {fmt(error_stats.get('syntaxErrorRate', error_stats.get('syntax_error_rate')), '%')} |")
        md_lines.append(f"| Runtime Error | {fmt(error_stats.get('runtimeErrorRate', error_stats.get('runtime_error_rate')), '%')} |")
        md_lines.append(f"| Timeout | {fmt(error_stats.get('timeoutRate', error_stats.get('timeout_rate')), '%')} |")
        md_lines.append(f"| Assertion Error | {fmt(error_stats.get('assertionErrorRate', error_stats.get('assertion_error_rate')), '%')} |")
        md_lines.append(f"| Import Error | {fmt(error_stats.get('importErrorRate', error_stats.get('import_error_rate')), '%')} |")
        md_lines.append(f"| Memory Error | {fmt(error_stats.get('memoryErrorRate', error_stats.get('memory_error_rate')), '%')} |")
        md_lines.append("")
        
        md_lines.append("### Execution Time Statistics")
        md_lines.append("")
        md_lines.append("| Metric | Value |")
        md_lines.append("|--------|-------|")
        md_lines.append(f"| Mean Runtime | {fmt(time_stats.get('meanRuntimeMs', time_stats.get('mean_runtime_ms')), ' ms')} |")
        md_lines.append(f"| P50 Runtime | {fmt(time_stats.get('p50RuntimeMs', time_stats.get('p50_runtime_ms')), ' ms')} |")
        md_lines.append(f"| P95 Runtime | {fmt(time_stats.get('p95RuntimeMs', time_stats.get('p95_runtime_ms')), ' ms')} |")
        md_lines.append(f"| Max Runtime | {fmt(time_stats.get('maxRuntimeMs', time_stats.get('max_runtime_ms')), ' ms')} |")
        md_lines.append("")
        
        # Environment information
        md_lines.append("## Environment")
        md_lines.append("")
        md_lines.append("| Component | Version |")
        md_lines.append("|-----------|---------|")
        md_lines.append(f"| OS | {fmt_na(system_info.get('os') or system_info.get('osVersion'))} |")
        md_lines.append(f"| Python | {fmt_na(system_info.get('python') or system_info.get('pythonVersion'))} |")
        md_lines.append(f"| PyTorch | {fmt_na(system_info.get('pytorch') or system_info.get('pytorchVersion'))} |")
        md_lines.append(f"| Transformers | {fmt_na(system_info.get('transformers') or system_info.get('transformersVersion'))} |")
        md_lines.append(f"| TRL | {fmt_na(system_info.get('trl') or system_info.get('trlVersion'))} |")
        md_lines.append(f"| PEFT | {fmt_na(system_info.get('peft') or system_info.get('peftVersion'))} |")
        md_lines.append(f"| CUDA | {fmt_na(system_info.get('cuda') or system_info.get('cudaVersion'))} |")
        md_lines.append(f"| cuDNN | {fmt_na(system_info.get('cudnn') or system_info.get('cudnnVersion'))} |")
        md_lines.append("")
        
        # Hardware information
        md_lines.append("## Hardware")
        md_lines.append("")
        md_lines.append("| Component | Details |")
        md_lines.append("|-----------|---------|")
        md_lines.append(f"| GPU | {fmt_na(system_info.get('gpu') or system_info.get('gpuModel'))} |")
        md_lines.append(f"| GPU Memory | {fmt_na(system_info.get('gpu_memory') or system_info.get('gpuMemoryGB'))} |")
        md_lines.append(f"| CPU | {fmt_na(system_info.get('cpu') or system_info.get('cpuModel'))} |")
        md_lines.append(f"| RAM | {fmt_na(system_info.get('ram') or system_info.get('ramGB'))} |")
        md_lines.append("")
        
        # =====================================================================
        # P2: Code Quality Metrics (eval reports only)
        # =====================================================================
        if is_eval_run and code_quality:
            md_lines.append("## Code Quality Metrics")
            md_lines.append("")
            md_lines.append("> These metrics analyze the quality of generated code.")
            md_lines.append("")
            md_lines.append("| Metric | Value | Description |")
            md_lines.append("|--------|-------|-------------|")
            md_lines.append(f"| Interface Compliance | {fmt(code_quality.get('interfaceComplianceRate', code_quality.get('interface_compliance_rate')), '%')} | Contains function definition |")
            md_lines.append(f"| Extra I/O Rate | {fmt(code_quality.get('extraIORate', code_quality.get('extra_io_rate')), '%')} | Contains print/input (may cause issues) |")
            md_lines.append(f"| Avg Code Length | {fmt(code_quality.get('avgCodeLength', code_quality.get('avg_code_length')), ' chars', 0)} | Average character count |")
            md_lines.append(f"| Avg Line Count | {fmt(code_quality.get('avgLineCount', code_quality.get('avg_line_count')), '', 1)} | Average lines per solution |")
            md_lines.append("")
            
            # P0-FIX: Extra I/O detailed explanation
            extra_io_rate = code_quality.get('extraIORate', code_quality.get('extra_io_rate', 0))
            if extra_io_rate and float(extra_io_rate) > 0:
                md_lines.append("> **📌 About Extra I/O Rate**")
                md_lines.append("> ")
                md_lines.append("> - `print()` statements: **Do not affect test results** (tests check return values, not stdout)")
                md_lines.append("> - `input()` statements: **Cause Timeout (TLE)** (code blocks waiting for stdin)")
                md_lines.append("> - **High Extra I/O Rate** indicates the model's training data is biased towards competitive programming I/O style.")
                md_lines.append("> - **Recommendation**: Consider prompt engineering or data cleaning to reduce I/O patterns.")
                md_lines.append("")
        
        # =====================================================================
        # Training Results (kabul-main style comprehensive loss statistics)
        # P0: Only shown in training reports, skip for eval reports
        # =====================================================================
        if not is_eval_run and deduplicated_metrics:
            md_lines.append("## Training Results")
            md_lines.append("")
            
            # 5.0 Per-Epoch Metrics (kabul-main style)
            # Group metrics by epoch
            # P0-FIX: HuggingFace Trainer epoch is in decimal form (e.g., 0.1, 0.2...), need to round up for grouping
            epochs_data = {}
            for m in deduplicated_metrics:
                raw_epoch = m.get("epoch")
                # If no epoch field, default to 1
                if raw_epoch is None:
                    epoch = 1
                else:
                    # Round up: 0.1->1, 0.9->1, 1.0->1, 1.1->2
                    epoch = max(1, int(raw_epoch) + (1 if raw_epoch % 1 > 0 else 0))
                if epoch not in epochs_data:
                    epochs_data[epoch] = {"losses": [], "eval_loss": None}
                if m.get("loss") is not None:
                    epochs_data[epoch]["losses"].append(m.get("loss"))
                if m.get("eval_loss") is not None:
                    epochs_data[epoch]["eval_loss"] = m.get("eval_loss")
            
            if len(epochs_data) >= 1:
                md_lines.append("### Per-Epoch Metrics")
                md_lines.append("")
                md_lines.append("| Epoch | Avg Train Loss | Min Loss | Max Loss | Eval Loss |")
                md_lines.append("|-------|---------------|----------|----------|-----------|")
                
                for ep in sorted(epochs_data.keys()):
                    losses = epochs_data[ep]["losses"]
                    avg_loss = sum(losses) / len(losses) if losses else 0
                    min_loss_ep = min(losses) if losses else None
                    max_loss_ep = max(losses) if losses else None
                    eval_loss = epochs_data[ep].get("eval_loss")
                    eval_str = f"{eval_loss:.4f}" if eval_loss else "N/A"
                    min_str = f"{min_loss_ep:.4f}" if min_loss_ep is not None else "N/A"
                    max_str = f"{max_loss_ep:.4f}" if max_loss_ep is not None else "N/A"
                    md_lines.append(f"| {int(ep)} | {avg_loss:.4f} | {min_str} | {max_str} | {eval_str} |")
                md_lines.append("")
            
            # Calculate key statistics (using filtered metrics)
            losses = [m.get("loss") for m in deduplicated_metrics if m.get("loss") is not None]
            lr_values = [m.get("lr") or m.get("learning_rate") for m in deduplicated_metrics if m.get("lr") or m.get("learning_rate")]
            
            if losses:
                initial_loss = losses[0]
                # Get first effective step number (for display)
                first_effective_step = deduplicated_metrics[0].get("step", 1) if deduplicated_metrics else 1
                # P0-FIX: Use valid final_loss (last step with lr)
                final_loss_val = get_valid_final_loss(deduplicated_metrics)
                if final_loss_val is None:
                    final_loss_val = losses[-1]  # fallback
                # Get last effective step number
                last_effective_step = deduplicated_metrics[-1].get("step", len(deduplicated_metrics)) if deduplicated_metrics else len(losses)
                min_loss = min(losses)
                max_loss = max(losses)
                avg_loss = sum(losses) / len(losses)
                loss_reduction = ((initial_loss - final_loss_val) / initial_loss * 100) if initial_loss > 0 else 0
                
                # Find convergence point (loss first drops below 0.1)
                convergence_step = None
                for i, loss in enumerate(losses):
                    if loss < 0.1:
                        convergence_step = deduplicated_metrics[i].get("step", i)
                        break
                
                # 5.1 Training Convergence Analysis
                md_lines.append("### Training Convergence Analysis")
                md_lines.append("")
                md_lines.append("| Metric | Value |")
                md_lines.append("|--------|-------|")
                # Use scientific-style labels: show first effective update step number
                md_lines.append(f"| Initial Loss (first effective update, Step {first_effective_step}) | {initial_loss:.4f} |")
                md_lines.append(f"| Final Loss (Step {last_effective_step}) | {final_loss_val:.4f} |")
                md_lines.append(f"| **Loss Reduction** | **{loss_reduction:.1f}%** |")
                md_lines.append(f"| Minimum Step Loss | {min_loss:.4f} |")
                md_lines.append(f"| Maximum Step Loss | {max_loss:.4f} |")
                md_lines.append(f"| Average Step Loss | {avg_loss:.4f} |")
                if convergence_step:
                    md_lines.append(f"| Convergence Step (<0.1 loss) | {convergence_step} |")
                md_lines.append(f"| Total Training Steps | {len(deduplicated_metrics)} |")
                md_lines.append("")
                # Add Final Loss definition note
                md_lines.append("> **Note:** Initial and final loss are from effective training steps (with non-zero learning rate). Pre-update warmup steps are excluded.")
                md_lines.append("")
                
                # 5.2 Learning Rate Schedule
                if lr_values:
                    max_lr = max(lr_values)
                    min_lr = min(lr_values)
                    scheduler_type = training_config.get('scheduler', 'cosine')
                    md_lines.append("### Learning Rate Schedule")
                    md_lines.append("")
                    md_lines.append("| Metric | Value |")
                    md_lines.append("|--------|-------|")
                    md_lines.append(f"| Max Learning Rate | {max_lr:.2e} |")
                    md_lines.append(f"| Min Learning Rate | {min_lr:.2e} |")
                    md_lines.append(f"| Schedule Type | {scheduler_type} |")
                    md_lines.append("")
                    # Add note for cosine scheduler with few steps
                    if scheduler_type.lower() == 'cosine' and len(deduplicated_metrics) <= 20:
                        md_lines.append("> **Note:** Due to the small number of training steps, the cosine schedule appears approximately linear.")
                        md_lines.append("")
                
                # 5.3 Loss Curve Sample Points
                md_lines.append("### Loss Curve Sample Points")
                md_lines.append("")
                md_lines.append("| Step | Loss | Learning Rate |")
                md_lines.append("|------|------|--------------|")
                
                # Use unified sampling function to get indices (from filtered metrics)
                sample_indices = uniform_sample_indices(len(deduplicated_metrics), losses, max_samples=30)
                
                for idx in sample_indices:
                    m = deduplicated_metrics[idx]
                    step = m.get("step", idx + 1)
                    loss = m.get("loss", 0)
                    lr = m.get("lr") or m.get("learning_rate")
                    lr_str = f"{lr:.2e}" if lr else "N/A"
                    md_lines.append(f"| {step} | {loss:.4f} | {lr_str} |")
                md_lines.append("")

                
                # 5.4 Training Progress Summary (kabul style)
                md_lines.append("### Training Progress Summary")
                md_lines.append("")
                md_lines.append(f"- **Initial Train Loss (Step {first_effective_step}):** {initial_loss:.4f}")
                md_lines.append(f"- **Final Train Loss (Step {last_effective_step}):** {final_loss_val:.4f}")
                md_lines.append(f"- **Loss Reduction:** {loss_reduction:.1f}%")
                if min_loss != final_loss_val:
                    md_lines.append(f"- **Best Step Loss:** {min_loss:.4f}")
                md_lines.append(f"- **Total Training Steps:** {len(deduplicated_metrics)} (Steps {first_effective_step}–{last_effective_step})")
                md_lines.append("")

                md_lines.append("")
        
        # Raw configuration
        md_lines.append("## Raw Configuration")
        md_lines.append("")
        md_lines.append("<details>")
        md_lines.append("<summary>Click to expand full configuration JSON</summary>")
        md_lines.append("")
        md_lines.append("```json")
        md_lines.append(json.dumps(self.config, indent=2, ensure_ascii=False))
        md_lines.append("```")
        md_lines.append("")
        md_lines.append("</details>")
        md_lines.append("")
        
        # Footer
        md_lines.append("---")
        md_lines.append("")
        md_lines.append(f"*Report generated by LLMTrainPipeline | {datetime.now().isoformat()}*")
        
        return "\n".join(md_lines)
    
    def generate_loss_curve_svg(self, width: int = 800, height: int = 250) -> str:
        """Generate training curve SVG"""
        if not self.metrics:
            return '<p style="color: #707080; text-align: center; padding: 40px;">No training data available</p>'
        
        padding = {"top": 30, "right": 50, "bottom": 50, "left": 70}
        chart_width = width - padding["left"] - padding["right"]
        chart_height = height - padding["top"] - padding["bottom"]
        
        # Extract data
        steps = [m.get("step", i) for i, m in enumerate(self.metrics)]
        losses = [m.get("loss", 0) for m in self.metrics]
        
        if not steps or not losses:
            return '<p style="color: #707080; text-align: center;">No loss data</p>'
            
        min_step, max_step = min(steps), max(steps)
        min_loss = min(losses) * 0.9
        max_loss = max(losses) * 1.1
        
        if max_step == min_step:
            max_step = min_step + 1
        if max_loss == min_loss:
            max_loss = min_loss + 0.1
            
        def scale_x(step):
            return padding["left"] + ((step - min_step) / (max_step - min_step)) * chart_width
            
        def scale_y(loss):
            return padding["top"] + chart_height - ((loss - min_loss) / (max_loss - min_loss)) * chart_height
        
        # Generate path
        path_points = []
        for i, (step, loss) in enumerate(zip(steps, losses)):
            x, y = scale_x(step), scale_y(loss)
            cmd = "M" if i == 0 else "L"
            path_points.append(f"{cmd} {x:.1f} {y:.1f}")
        path_data = " ".join(path_points)
        
        # Y-axis ticks
        y_ticks = []
        for t in [0, 0.25, 0.5, 0.75, 1.0]:
            val = min_loss + t * (max_loss - min_loss)
            y = scale_y(val)
            y_ticks.append(f'<line x1="{padding["left"]}" y1="{y:.1f}" x2="{width - padding["right"]}" y2="{y:.1f}" stroke="#3a3a5a" stroke-dasharray="4"/>')
            y_ticks.append(f'<text x="{padding["left"] - 10}" y="{y + 4:.1f}" text-anchor="end" fill="#a0a0b0" font-size="12">{val:.3f}</text>')
        
        # X-axis ticks
        x_ticks = []
        for t in [0, 0.25, 0.5, 0.75, 1.0]:
            val = min_step + t * (max_step - min_step)
            x = scale_x(val)
            x_ticks.append(f'<text x="{x:.1f}" y="{height - padding["bottom"] + 20}" text-anchor="middle" fill="#a0a0b0" font-size="12">{int(val)}</text>')
        
        svg = f'''
        <svg viewBox="0 0 {width} {height}" style="width: 100%; height: auto; max-height: 300px;">
            <!-- Grid -->
            {"".join(y_ticks)}
            
            <!-- Axes -->
            <line x1="{padding['left']}" y1="{padding['top']}" x2="{padding['left']}" y2="{height - padding['bottom']}" stroke="#4a4a6a" stroke-width="2"/>
            <line x1="{padding['left']}" y1="{height - padding['bottom']}" x2="{width - padding['right']}" y2="{height - padding['bottom']}" stroke="#4a4a6a" stroke-width="2"/>
            
            <!-- X Labels -->
            {"".join(x_ticks)}
            
            <!-- Axis Titles -->
            <text x="{padding['left'] - 50}" y="{height // 2}" text-anchor="middle" fill="#707080" font-size="12" transform="rotate(-90 {padding['left'] - 50} {height // 2})">Loss</text>
            <text x="{width // 2}" y="{height - 10}" text-anchor="middle" fill="#707080" font-size="12">Step</text>
            
            <!-- Loss Curve -->
            <path d="{path_data}" fill="none" stroke="#4a9eff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
            
            <!-- Start Point -->
            <circle cx="{scale_x(steps[0]):.1f}" cy="{scale_y(losses[0]):.1f}" r="4" fill="#f59e0b"/>
            
            <!-- End Point -->
            <circle cx="{scale_x(steps[-1]):.1f}" cy="{scale_y(losses[-1]):.1f}" r="5" fill="#10b981"/>
            
            <!-- Legend -->
            <circle cx="{width - padding['right'] - 60}" cy="20" r="4" fill="#f59e0b"/>
            <text x="{width - padding['right'] - 50}" y="24" fill="#a0a0b0" font-size="11">Start</text>
            <circle cx="{width - padding['right'] - 60}" cy="38" r="4" fill="#10b981"/>
            <text x="{width - padding['right'] - 50}" y="42" fill="#a0a0b0" font-size="11">End</text>
        </svg>
        '''
        return svg
    
    def generate_loss_table_html(self, metrics: List[Dict[str, Any]]) -> str:
        """Generate detailed Loss data table HTML"""
        if not metrics:
            return ''
        
        # Statistics
        total_points = len(metrics)
        losses = [m.get("loss", 0) for m in metrics if m.get("loss") is not None]
        
        min_loss = min(losses) if losses else None
        max_loss = max(losses) if losses else None
        avg_loss = sum(losses) / len(losses) if losses else None
        
        # =====================================================================
        # Calculate Per-Epoch statistics
        # P0-FIX: HuggingFace Trainer epoch is in decimal form (e.g., 0.1, 0.2...), need to round up for grouping
        # =====================================================================
        epochs_data = {}
        for m in metrics:
            raw_epoch = m.get("epoch")
            # If no epoch field, default to 1
            if raw_epoch is None:
                epoch = 1
            else:
                # Round up: 0.1->1, 0.9->1, 1.0->1, 1.1->2 (ceiling logic)
                epoch = max(1, math.ceil(raw_epoch) if raw_epoch % 1 > 0 else int(raw_epoch) if raw_epoch > 0 else 1)
            if epoch not in epochs_data:
                epochs_data[epoch] = {"losses": [], "eval_loss": None, "lr_values": []}
            if m.get("loss") is not None:
                epochs_data[epoch]["losses"].append(m.get("loss"))
            if m.get("eval_loss") is not None:
                epochs_data[epoch]["eval_loss"] = m.get("eval_loss")
            lr = m.get("lr") or m.get("learning_rate")
            if lr is not None:
                epochs_data[epoch]["lr_values"].append(lr)
        
        # Generate Per-Epoch table rows
        epoch_rows = []
        for ep in sorted(epochs_data.keys()):
            ep_losses = epochs_data[ep]["losses"]
            avg_ep_loss = sum(ep_losses) / len(ep_losses) if ep_losses else None
            min_ep_loss = min(ep_losses) if ep_losses else None
            max_ep_loss = max(ep_losses) if ep_losses else None
            eval_loss = epochs_data[ep].get("eval_loss")
            lr_values = epochs_data[ep]["lr_values"]
            final_lr = lr_values[-1] if lr_values else None
            
            epoch_rows.append(f'''
                <tr>
                    <td style="font-weight: 600;">{int(ep)}</td>
                    <td>{f"{avg_ep_loss:.6f}" if avg_ep_loss is not None else "N/A"}</td>
                    <td>{f"{min_ep_loss:.6f}" if min_ep_loss is not None else "N/A"}</td>
                    <td>{f"{max_ep_loss:.6f}" if max_ep_loss is not None else "N/A"}</td>
                    <td>{f"{eval_loss:.6f}" if eval_loss is not None else "N/A"}</td>
                    <td>{f"{final_lr:.2e}" if final_lr is not None else "N/A"}</td>
                </tr>
            ''')
        
        # Per-Epoch HTML section (display when there are multiple epochs or user may care)
        per_epoch_html = ""
        if len(epochs_data) >= 1:
            per_epoch_html = f'''
            <h3 style="margin-top: 24px;">Per-Epoch Statistics</h3>
            <table>
                <thead>
                    <tr>
                        <th>Epoch</th>
                        <th>Avg Loss</th>
                        <th>Min Loss</th>
                        <th>Max Loss</th>
                        <th>Eval Loss</th>
                        <th>Final LR</th>
                    </tr>
                </thead>
                <tbody>
                    {"".join(epoch_rows)}
                </tbody>
            </table>
            '''
        
        # Find step corresponding to minimum loss
        min_loss_step = None
        for m in metrics:
            if m.get("loss") == min_loss:
                min_loss_step = m.get("step")
                break
        
        # Generate summary table (showing key points: start, end, lowest + uniform sampling)
        summary_rows = []
        
        # Use unified sampling function to get indices
        sample_indices = uniform_sample_indices(len(metrics), losses, max_samples=30)
        
        for idx in sample_indices:
            m = metrics[idx]
            step = m.get("step", idx)
            epoch = m.get("epoch", "")
            loss = m.get("loss")
            lr = m.get("lr") or m.get("learning_rate")
            grad_norm = m.get("grad_norm") or m.get("gradNorm")
            
            loss_class = "highlight" if loss == min_loss else ""
            
            summary_rows.append(f'''
                <tr>
                    <td>{step}</td>
                    <td>{epoch if epoch else '-'}</td>
                    <td class="{loss_class}">{f"{loss:.6f}" if loss is not None else 'N/A'}</td>
                    <td>{f"{float(lr):.2e}" if lr is not None else 'N/A'}</td>
                    <td>{f"{float(grad_norm):.4f}" if grad_norm is not None else 'N/A'}</td>
                </tr>
            ''')
        
        # Generate expandable table for full data
        all_rows = []
        for m in metrics:
            step = m.get("step", 0)
            epoch = m.get("epoch", "")
            loss = m.get("loss")
            lr = m.get("lr") or m.get("learning_rate")
            grad_norm = m.get("grad_norm") or m.get("gradNorm")
            
            all_rows.append(f'''
                <tr>
                    <td>{step}</td>
                    <td>{epoch if epoch else '-'}</td>
                    <td>{f"{loss:.6f}" if loss is not None else 'N/A'}</td>
                    <td>{f"{float(lr):.2e}" if lr is not None else 'N/A'}</td>
                    <td>{f"{float(grad_norm):.4f}" if grad_norm is not None else 'N/A'}</td>
                </tr>
            ''')
        
        return f'''
        <div class="section">
            <h2><span class="icon">📊</span> Training Metrics Log</h2>
            
            <!-- Statistics Summary -->
            <div class="metrics-summary" style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 20px;">
                <div class="summary-item" style="background: var(--bg-tertiary); padding: 12px; border-radius: 8px; text-align: center;">
                    <div style="color: var(--text-secondary); font-size: 12px;">Total Steps</div>
                    <div style="color: var(--accent); font-size: 18px; font-weight: 600;">{total_points}</div>
                </div>
                <div class="summary-item" style="background: var(--bg-tertiary); padding: 12px; border-radius: 8px; text-align: center;">
                    <div style="color: var(--text-secondary); font-size: 12px;">Min Loss (Step {min_loss_step})</div>
                    <div style="color: var(--success); font-size: 18px; font-weight: 600;">{f"{min_loss:.6f}" if min_loss is not None else 'N/A'}</div>
                </div>
                <div class="summary-item" style="background: var(--bg-tertiary); padding: 12px; border-radius: 8px; text-align: center;">
                    <div style="color: var(--text-secondary); font-size: 12px;">Max Loss</div>
                    <div style="color: var(--warning); font-size: 18px; font-weight: 600;">{f"{max_loss:.6f}" if max_loss is not None else 'N/A'}</div>
                </div>
                <div class="summary-item" style="background: var(--bg-tertiary); padding: 12px; border-radius: 8px; text-align: center;">
                    <div style="color: var(--text-secondary); font-size: 12px;">Avg Loss</div>
                    <div style="color: var(--text-primary); font-size: 18px; font-weight: 600;">{f"{avg_loss:.6f}" if avg_loss is not None else 'N/A'}</div>
                </div>
            </div>
            
            <!-- Per-Epoch Statistics Table -->
            {per_epoch_html}
            
            <!-- Summary Table -->
            <h3>Key Data Points</h3>
            <table>
                <thead>
                    <tr>
                        <th>Step</th>
                        <th>Epoch</th>
                        <th>Loss</th>
                        <th>Learning Rate</th>
                        <th>Grad Norm</th>
                    </tr>
                </thead>
                <tbody>
                    {"".join(summary_rows)}
                </tbody>
            </table>
            
            <!-- Full Data (Expandable) -->
            <details class="raw-data" style="margin-top: 20px;">
                <summary>📋 View All {total_points} Data Points</summary>
                <div style="max-height: 400px; overflow-y: auto;">
                    <table style="font-size: 12px;">
                        <thead>
                            <tr>
                                <th>Step</th>
                                <th>Epoch</th>
                                <th>Loss</th>
                                <th>Learning Rate</th>
                                <th>Grad Norm</th>
                            </tr>
                        </thead>
                        <tbody>
                            {"".join(all_rows)}
                        </tbody>
                    </table>
                </div>
            </details>
        </div>
        '''
    
    def generate_html(self, title: Optional[str] = None) -> str:
        """Generate extremely detailed and comprehensive HTML report"""
        
        # =====================================================================
        # P0: Data preprocessing - deduplicate metrics
        # =====================================================================
        deduplicated_metrics = deduplicate_metrics(self.metrics)
        
        # Extract data from each section
        training_config = self.config.get("training", {})
        lora_config = self.config.get("lora", {})
        model_config = self.config.get("model", {})
        dataset_config = self.config.get("dataset", {})
        
        # =====================================================================
        # P0-1: Auto-fix dataset stats - total_samples cannot be less than train_samples
        # =====================================================================
        total_samples = dataset_config.get("samples", 0) or 0
        train_samples = dataset_config.get("train_samples", 0) or 0
        if total_samples < train_samples:
            # Auto-fix: use train_samples as total
            dataset_config["samples"] = train_samples
        elif total_samples == 0 and train_samples > 0:
            dataset_config["samples"] = train_samples
        
        # System info (prefer recorded, otherwise collect current)
        # Note: empty dict {} is also treated as no data, need to collect current system info
        system_info = self.experiment_meta if self.experiment_meta else self.collect_system_info()
        
        # Run information
        run_name = title or self.run_info.get("name", self.config.get("run_name", "Training Run"))
        run_id = self.run_info.get("id", "N/A")
        start_time = self.run_info.get("start_time", self.config.get("start_time", ""))
        end_time = self.run_info.get("end_time", self.config.get("end_time", ""))
        duration = self.run_info.get("duration", "")
        seed = self.config.get("seed", training_config.get("seed", "N/A"))
        git_commit = self.run_info.get("git_commit", "N/A")
        
        # =====================================================================
        # P0: Training steps statistics - distinguish three different concepts (consistent with Markdown report)
        # =====================================================================
        # 1. Planned steps: steps planned in configuration
        planned_steps = training_config.get("total_steps") or training_config.get("planned_steps")
        
        # 2. Raw logged steps: total steps recorded in raw logs (including warmup/pre-log)
        # Prioritize value passed from Node.js
        raw_logged_steps_from_config = training_config.get("raw_logged_steps")
        raw_logged_steps = raw_logged_steps_from_config if raw_logged_steps_from_config else (len(self.metrics) if self.metrics else 0)
        
        # 3. Effective update steps: steps where parameter updates actually occurred
        # Use actual length of deduplicated_metrics filtered by Python (most accurate)
        effective_steps = len(deduplicated_metrics) if deduplicated_metrics else 0
        
        # total_steps for display (prefer effective_steps)
        total_steps = effective_steps if effective_steps > 0 else (planned_steps or "N/A")
        
        # Calculate warmup steps (raw logged - effective steps)
        warmup_steps = raw_logged_steps - effective_steps if raw_logged_steps > effective_steps else 0
        
        # =====================================================================
        # P1-2: Final Loss - get last valid train_step loss (non-summary)
        # =====================================================================
        final_loss = None
        if deduplicated_metrics:
            # P0-FIX: Prefer to find last step with lr (exclude epoch average loss)
            for m in reversed(deduplicated_metrics):
                loss = m.get("loss")
                lr = m.get("lr") or m.get("learning_rate")
                if loss is not None and loss > 0 and lr is not None:
                    final_loss = loss
                    break
            
            # If no step with lr found, use second to last (avoid using possible epoch average)
            if final_loss is None and len(deduplicated_metrics) >= 2:
                final_loss = deduplicated_metrics[-2].get("loss")
            
            # Last fallback
            if final_loss is None and deduplicated_metrics:
                final_loss = deduplicated_metrics[-1].get("loss")
        
        # Get first and last effective step numbers (for display)
        first_effective_step = deduplicated_metrics[0].get("step", 1) if deduplicated_metrics else 1
        last_effective_step = deduplicated_metrics[-1].get("step", effective_steps) if deduplicated_metrics else effective_steps
        
        # LoRA statistics
        lora_stats = self.lora_stats or {}
        trainable_params = lora_stats.get("trainable_params")
        total_params = lora_stats.get("total_params")
        trainable_percent = lora_stats.get("trainable_percent")
        
        # Evaluation results
        eval_result = self.eval_result or {}
        pass_at_1 = eval_result.get("pass_at_1") or eval_result.get("passAt1")
        pass_at_5 = get_value(eval_result, "pass_at_k", "5") or get_value(eval_result, "passAtK", "5")
        pass_at_10 = get_value(eval_result, "pass_at_k", "10") or get_value(eval_result, "passAtK", "10")
        compile_rate = eval_result.get("compile_rate") or eval_result.get("compileRate")
        
        error_stats = eval_result.get("error_stats", eval_result.get("errorStats", {}))
        time_stats = eval_result.get("time_stats", eval_result.get("timeStats", {}))
        
        # =====================================================================
        # P0: Data validation
        # =====================================================================
        validator = DataValidator()
        
        # Validate dataset stats
        validator.validate_dataset_stats(dataset_config)
        
        # Validate steps
        validator.validate_steps(planned_steps, effective_steps, len(deduplicated_metrics))
        
        # Validate learning rate
        config_lr = training_config.get("lr") or training_config.get("learning_rate")
        lr_values = extract_lr_values(deduplicated_metrics)
        initial_lr = lr_values[0] if lr_values else None
        validator.validate_learning_rate(str(config_lr) if config_lr else None, initial_lr)
        
        # Validate scheduler
        scheduler_config = training_config.get("scheduler", "cosine")
        detected_scheduler = validator.validate_scheduler(scheduler_config, lr_values)
        
        # Collect all warnings
        validation_warnings = validator.get_all_warnings()
        
        # Formatting function
        def fmt(val, suffix="", decimals=2):
            if val is None:
                return "N/A"
            try:
                return f"{float(val):.{decimals}f}{suffix}"
            except:
                return str(val)
        
        def fmt_na(val):
            return str(val) if val is not None else '<span class="muted">Not collected</span>'
        
        # Generate training curve - use deduplicated metrics
        # Temporarily replace self.metrics to generate curve
        original_metrics = self.metrics
        self.metrics = deduplicated_metrics
        loss_curve_svg = self.generate_loss_curve_svg()
        self.metrics = original_metrics
        
        # =====================================================================
        # Generate detailed Loss data table
        # =====================================================================
        loss_table_html = self.generate_loss_table_html(deduplicated_metrics)
        
        # Generate checkpoint list
        checkpoints_html = ""
        if self.checkpoints:
            items = []
            for cp in self.checkpoints:
                step = cp.get("step", "N/A")
                epoch = cp.get("epoch", "")
                loss = cp.get("loss")
                items.append(f'''
                    <div class="checkpoint-item">
                        <span class="step">Step {step}</span>
                        {f'<span class="epoch">(Epoch {epoch})</span>' if epoch else ''}
                        {f'<span class="loss">Loss: {loss:.4f}</span>' if loss else ''}
                    </div>
                ''')
            checkpoints_html = f'''
            <div class="section">
                <h2><span class="icon">💾</span> Checkpoints ({len(self.checkpoints)})</h2>
                <div class="checkpoints-list">
                    {"".join(items)}
                </div>
            </div>
            '''
        
        # =====================================================================
        # P0: Generate warning banner HTML
        # =====================================================================
        warnings_html = ""
        if validation_warnings:
            warning_items = "".join([f'<div class="warning-item">⚠ {w}</div>' for w in validation_warnings])
            warnings_html = f'''
    <div class="warnings-banner">
        <div class="warnings-title">⚠ Data Consistency Warnings</div>
        {warning_items}
    </div>
'''
        
        # =====================================================================
        # P0: Evaluation status display
        # =====================================================================
        eval_not_run = not self.eval_result or (pass_at_1 is None and compile_rate is None)
        eval_status_msg = ""
        if eval_not_run:
            eval_status_msg = '<div class="eval-not-run">📋 Evaluation Not Run - Code evaluation was not performed, no data for Pass@k and Compile Rate metrics</div>'
        
        html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{run_name} - Complete Training Report</title>
    <style>
        :root {{
            --bg-primary: #0f0f1a;
            --bg-secondary: #1a1a2e;
            --bg-tertiary: #252540;
            --bg-card: #2d2d4a;
            --text-primary: #f0f0f5;
            --text-secondary: #a0a0b0;
            --text-muted: #606070;
            --accent: #4a9eff;
            --success: #10b981;
            --warning: #f59e0b;
            --error: #ef4444;
            --border: #3a3a5a;
        }}
        
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        
        body {{
            font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.6;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 40px 24px;
        }}
        
        /* Warnings Banner */
        .warnings-banner {{
            background: linear-gradient(135deg, #4a2020, #3a1a1a);
            border: 1px solid #ef4444;
            border-radius: 12px;
            padding: 16px 20px;
            margin-bottom: 24px;
        }}
        
        .warnings-banner .warnings-title {{
            color: #ef4444;
            font-weight: 600;
            font-size: 14px;
            margin-bottom: 12px;
        }}
        
        .warnings-banner .warning-item {{
            color: #fca5a5;
            font-size: 13px;
            padding: 6px 0;
            border-bottom: 1px solid rgba(239, 68, 68, 0.2);
        }}
        
        .warnings-banner .warning-item:last-child {{
            border-bottom: none;
        }}
        
        /* Eval Not Run Notice */
        .eval-not-run {{
            background: linear-gradient(135deg, #2a2040, #1a1530);
            border: 1px solid #8b5cf6;
            border-radius: 8px;
            padding: 12px 16px;
            margin-bottom: 16px;
            color: #c4b5fd;
            font-size: 13px;
        }}
        
        /* Reproducibility Section */
        .repro-table {{
            font-size: 13px;
        }}
        
        .repro-table th {{
            width: 30%;
        }}
        
        /* Header */
        .header {{
            text-align: center;
            margin-bottom: 48px;
            padding-bottom: 32px;
            border-bottom: 1px solid var(--border);
        }}
        
        .header h1 {{
            color: var(--accent);
            font-size: 2.5rem;
            font-weight: 700;
            margin-bottom: 16px;
        }}
        
        .header .meta {{
            display: flex;
            flex-wrap: wrap;
            justify-content: center;
            gap: 12px;
            color: var(--text-secondary);
            font-size: 14px;
        }}
        
        .header .meta-item {{
            background: var(--bg-secondary);
            padding: 8px 16px;
            border-radius: 8px;
            border: 1px solid var(--border);
        }}
        
        .header .meta-item strong {{
            color: var(--text-primary);
        }}
        
        /* Metrics Grid */
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 16px;
            margin-bottom: 40px;
        }}
        
        .metric-card {{
            background: linear-gradient(135deg, var(--bg-tertiary), var(--bg-secondary));
            border-radius: 16px;
            padding: 24px;
            text-align: center;
            border: 1px solid var(--border);
        }}
        
        .metric-card .value {{
            font-size: 2rem;
            font-weight: 700;
            color: var(--accent);
            line-height: 1;
            margin-bottom: 8px;
        }}
        
        .metric-card .value.success {{ color: var(--success); }}
        .metric-card .value.warning {{ color: var(--warning); }}
        .metric-card .value.error {{ color: var(--error); }}
        
        .metric-card .label {{
            color: var(--text-secondary);
            font-size: 13px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        
        /* Section */
        .section {{
            background: var(--bg-secondary);
            border-radius: 16px;
            padding: 28px;
            margin-bottom: 24px;
            border: 1px solid var(--border);
        }}
        
        .section h2 {{
            color: var(--accent);
            font-size: 1.25rem;
            font-weight: 600;
            margin-bottom: 20px;
            padding-bottom: 12px;
            border-bottom: 1px solid var(--border);
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        
        .section h2 .icon {{
            font-size: 1.4rem;
        }}
        
        .section h3 {{
            color: var(--text-secondary);
            font-size: 14px;
            margin: 20px 0 12px 0;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        
        /* Table */
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
        }}
        
        th, td {{
            padding: 12px 16px;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }}
        
        th {{
            color: var(--text-secondary);
            font-weight: 500;
            width: 40%;
            background: rgba(0,0,0,0.2);
        }}
        
        td {{
            font-family: 'JetBrains Mono', 'Fira Code', monospace;
            color: var(--text-primary);
        }}
        
        td.highlight {{ color: var(--accent); font-weight: 600; }}
        td.success {{ color: var(--success); }}
        td.warning {{ color: var(--warning); }}
        td.error {{ color: var(--error); }}
        .muted {{ color: var(--text-muted); font-style: italic; }}
        
        /* Two Column */
        .two-col {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 24px;
        }}
        
        @media (max-width: 768px) {{
            .two-col {{ grid-template-columns: 1fr; }}
        }}
        
        /* Chart */
        .chart-container {{
            background: var(--bg-tertiary);
            border-radius: 12px;
            padding: 24px;
            margin-top: 16px;
        }}
        
        /* Checkpoints */
        .checkpoints-list {{
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
        }}
        
        .checkpoint-item {{
            background: var(--bg-tertiary);
            padding: 12px 16px;
            border-radius: 8px;
            font-size: 13px;
            border: 1px solid var(--border);
        }}
        
        .checkpoint-item .step {{
            color: var(--accent);
            font-weight: 600;
        }}
        
        .checkpoint-item .epoch,
        .checkpoint-item .loss {{
            color: var(--text-secondary);
            margin-left: 8px;
        }}
        
        /* Raw Data */
        .raw-data {{
            background: var(--bg-tertiary);
            border-radius: 12px;
            padding: 16px;
            margin-top: 16px;
        }}
        
        .raw-data summary {{
            cursor: pointer;
            color: var(--text-secondary);
            font-size: 14px;
            font-weight: 500;
            padding: 8px 0;
        }}
        
        .raw-data pre {{
            background: var(--bg-primary);
            padding: 16px;
            border-radius: 8px;
            overflow-x: auto;
            font-size: 12px;
            line-height: 1.5;
            color: var(--text-secondary);
            margin-top: 12px;
            max-height: 400px;
            overflow-y: auto;
        }}
        
        /* Footer */
        footer {{
            margin-top: 48px;
            text-align: center;
            color: var(--text-muted);
            font-size: 12px;
            padding: 24px;
            border-top: 1px solid var(--border);
        }}
    </style>
</head>
<body>
<div class="container">
    <!-- Header -->
    <div class="header">
        <h1>🧪 {run_name}</h1>
        <div class="meta">
            <div class="meta-item">Run ID: <strong>{run_id}</strong></div>
            <div class="meta-item">Duration: <strong>{duration or 'N/A'}</strong></div>
            <div class="meta-item">Seed: <strong>{seed}</strong></div>
            {f'<div class="meta-item">Git: <strong>{git_commit[:7]}</strong></div>' if git_commit and git_commit != "N/A" else ''}
            <div class="meta-item">Generated: <strong>{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</strong></div>
        </div>
    </div>

    <!-- Warnings Banner (P0: Data Consistency Checks) -->
    {warnings_html}

    <!-- Key Metrics -->
    <div class="section">
        <h2><span class="icon">📊</span> Key Metrics</h2>
        <table>
            <tr><th>Pass@1</th><td class="highlight">{fmt(pass_at_1, '%')}</td></tr>
            <tr><th>Compile Rate</th><td>{fmt(compile_rate, '%')}</td></tr>
            <tr><th>Final Loss</th><td>{fmt(final_loss, '', 4) if final_loss else 'N/A'}</td></tr>
            {f'<tr><th>Planned Steps</th><td>{planned_steps}</td></tr>' if planned_steps and (raw_logged_steps != effective_steps or planned_steps != effective_steps) else ''}
            {f'<tr><th>Logged Steps</th><td>{raw_logged_steps}</td></tr>' if planned_steps and raw_logged_steps != effective_steps else ''}
            {f'<tr><th><strong>Effective Update Steps</strong></th><td class="highlight"><strong>{effective_steps}</strong></td></tr>' if planned_steps and (raw_logged_steps != effective_steps or planned_steps != effective_steps) else f'<tr><th>Total Steps</th><td>{total_steps}</td></tr>'}
            <tr><th>Trainable Params</th><td>{format_number(trainable_params)}</td></tr>
            <tr><th>Trainable %</th><td>{fmt(trainable_percent, '%', 4) if trainable_percent else 'N/A'}</td></tr>
        </table>
    </div>
    
    {f'''<div style="background: rgba(59, 130, 246, 0.1); border: 1px solid rgba(59, 130, 246, 0.3); border-radius: 8px; padding: 12px 16px; margin-bottom: 20px; font-size: 13px; color: #93c5fd;">
        <strong>ℹ️ Note:</strong> Steps 1–{first_effective_step - 1} are pre-update logs during warmup/gradient accumulation (lr=0). 
        Effective parameter updates: {effective_steps} steps (Steps {first_effective_step}–{last_effective_step}).
        {f"Planned: {planned_steps}, Logged: {raw_logged_steps}." if planned_steps else ""}
    </div>''' if warmup_steps > 0 else ''}

    <!-- Training Loss Curve -->
    {'<div class="section"><h2><span class="icon">📈</span> Training Loss Curve</h2><div class="chart-container">' + loss_curve_svg + '</div></div>' if self.metrics else ''}

    <!-- Training Metrics Log Table -->
    {loss_table_html}

    <!-- Model & Dataset -->
    <div class="two-col">
        <div class="section">
            <h2><span class="icon">🤖</span> Base Model</h2>
            <table>
                <tr><th>Model Name</th><td class="highlight">{fmt_na(model_config.get("name", self.config.get("model_name")))}</td></tr>
                <tr><th>Model Path</th><td>{fmt_na(model_config.get("path", self.config.get("model_path")))}</td></tr>
                <tr><th>Parameters</th><td>{fmt_na(model_config.get("params"))}</td></tr>
                <tr><th>Quantization</th><td>{fmt_na(lora_config.get("quantization", "None"))}</td></tr>
            </table>
        </div>
        <div class="section">
            <h2><span class="icon">📊</span> Dataset</h2>
            <table>
                <tr><th>Dataset Name</th><td class="highlight">{fmt_na(dataset_config.get("name", self.config.get("dataset_name")))}</td></tr>
                <tr><th>Dataset Path</th><td>{fmt_na(dataset_config.get("path", self.config.get("dataset_path")))}</td></tr>
                <tr><th>Total Samples</th><td>{fmt_na(dataset_config.get("samples"))}</td></tr>
                <tr><th>Train Samples</th><td>{fmt_na(dataset_config.get("train_samples"))}</td></tr>
                <tr><th>Total Tokens</th><td>{format_number(dataset_config.get("total_tokens"))}</td></tr>
            </table>
        </div>
    </div>

    <!-- Environment & Hardware -->
    <div class="two-col">
        <div class="section">
            <h2><span class="icon">🖥️</span> Environment</h2>
            <table>
                <tr><th>Operating System</th><td>{fmt_na(system_info.get("os") or system_info.get("osVersion"))}</td></tr>
                <tr><th>Python</th><td>{fmt_na(system_info.get("python") or system_info.get("pythonVersion"))}</td></tr>
                <tr><th>PyTorch</th><td>{fmt_na(system_info.get("pytorch") or system_info.get("pytorchVersion"))}</td></tr>
                <tr><th>Transformers</th><td>{fmt_na(system_info.get("transformers") or system_info.get("transformersVersion"))}</td></tr>
                <tr><th>TRL</th><td>{fmt_na(system_info.get("trl") or system_info.get("trlVersion"))}</td></tr>
                <tr><th>PEFT</th><td>{fmt_na(system_info.get("peft") or system_info.get("peftVersion"))}</td></tr>
                <tr><th>CUDA</th><td>{fmt_na(system_info.get("cuda") or system_info.get("cudaVersion"))}</td></tr>
                <tr><th>cuDNN</th><td>{fmt_na(system_info.get("cudnn") or system_info.get("cudnnVersion"))}</td></tr>
                <tr><th>bitsandbytes</th><td>{fmt_na(system_info.get("bitsandbytes") or system_info.get("bitsandbytesVersion"))}</td></tr>
            </table>
        </div>
        <div class="section">
            <h2><span class="icon">⚡</span> Hardware</h2>
            <table>
                <tr><th>GPU</th><td class="highlight">{fmt_na(system_info.get("gpu") or system_info.get("gpuModel"))}</td></tr>
                <tr><th>GPU Memory</th><td>{fmt_na(system_info.get("gpu_memory") or system_info.get("gpuMemoryGB"))}</td></tr>
                <tr><th>CPU</th><td>{fmt_na(system_info.get("cpu") or system_info.get("cpuModel"))}</td></tr>
                <tr><th>RAM</th><td>{fmt_na(system_info.get("ram") or system_info.get("ramGB"))}</td></tr>
            </table>
        </div>
    </div>

    <!-- Training Configuration -->
    <div class="section">
        <h2><span class="icon">⚙️</span> Training Configuration (Complete)</h2>
        <div class="two-col">
            <table>
                <tr><th>Batch Size (per device)</th><td>{training_config.get("batchSize", training_config.get("batch_size", "N/A"))}</td></tr>
                <tr><th>Gradient Accumulation</th><td>{training_config.get("gradientAccumulation", training_config.get("gradient_accumulation", training_config.get("gradAccum", "N/A")))}</td></tr>
                <tr><th>Effective Batch Size</th><td class="highlight">{training_config.get("batchSize", 1) * training_config.get("gradientAccumulation", training_config.get("gradAccum", 8))}</td></tr>
                <tr><th>Learning Rate</th><td>{training_config.get("lr", training_config.get("learning_rate", "N/A"))}</td></tr>
                <tr><th>LR Scheduler</th><td>{training_config.get("scheduler", training_config.get("lr_scheduler", "N/A"))}</td></tr>
                <tr><th>Warmup Ratio</th><td>{training_config.get("warmupRatio", training_config.get("warmup_ratio", "N/A"))}</td></tr>
            </table>
            <table>
                <tr><th>Epochs</th><td>{training_config.get("epochs", training_config.get("num_epochs", "N/A"))}</td></tr>
                <tr><th>Max Sequence Length</th><td>{training_config.get("maxSeqLen", training_config.get("max_seq_length", training_config.get("maxLength", "N/A")))}</td></tr>
                <tr><th>Optimizer</th><td>{training_config.get("optimizer", "N/A")}</td></tr>
                <tr><th>Weight Decay</th><td>{training_config.get("weightDecay", training_config.get("weight_decay", "N/A"))}</td></tr>
                <tr><th>Precision</th><td>{training_config.get("precision", training_config.get("mixed_precision", "N/A"))}</td></tr>
                <tr><th>Total Steps</th><td class="highlight">{total_steps}</td></tr>
            </table>
        </div>
    </div>

    <!-- LoRA Configuration -->
    {f'''
    <div class="section">
        <h2><span class="icon">🔧</span> LoRA Configuration (Complete)</h2>
        <div class="two-col">
            <table>
                <tr><th>Enabled</th><td>{'Yes' if lora_config.get("enabled", True) else 'No'}</td></tr>
                <tr><th>Rank (r)</th><td>{fmt_na(lora_config.get("rank", lora_config.get("r")))}</td></tr>
                <tr><th>Alpha</th><td>{fmt_na(lora_config.get("alpha", lora_config.get("lora_alpha")))}</td></tr>
                <tr><th>Dropout</th><td>{fmt_na(lora_config.get("dropout", lora_config.get("lora_dropout")))}</td></tr>
            </table>
            <table>
                <tr><th>Target Modules</th><td>{", ".join(lora_config.get("targetModules", lora_config.get("target_modules", []))) or "N/A"}</td></tr>
                <tr><th>Quantization</th><td>{fmt_na(lora_config.get("quantization"))}</td></tr>
                <tr><th>Trainable Parameters</th><td class="highlight">{format_number(trainable_params)}</td></tr>
                <tr><th>Total Parameters</th><td>{format_number(total_params)}</td></tr>
                <tr><th>Trainable Percentage</th><td class="highlight">{fmt(trainable_percent, '%', 4) if trainable_percent else 'N/A'}</td></tr>
            </table>
        </div>
    </div>
    ''' if lora_config.get("enabled", True) else ''}

    <!-- Evaluation Results -->
    <div class="section">
        <h2><span class="icon">🎯</span> Evaluation Results (Complete)</h2>
        {eval_status_msg}
        <div class="two-col">
            <div>
                <h3>Pass@k Metrics</h3>
                <table>
                    <tr><th>Pass@1</th><td class="highlight success">{fmt(pass_at_1, '%')}</td></tr>
                    <tr><th>Pass@5</th><td>{fmt(pass_at_5, '%')}</td></tr>
                    <tr><th>Pass@10</th><td>{fmt(pass_at_10, '%')}</td></tr>
                    <tr><th>Compile Rate</th><td>{fmt(compile_rate, '%')}</td></tr>
                </table>
            </div>
            <div>
                <h3>Error Distribution</h3>
                <table>
                    <tr><th>Syntax Error</th><td class="error">{fmt(error_stats.get("syntaxErrorRate", error_stats.get("syntax_error_rate")), '%')}</td></tr>
                    <tr><th>Runtime Error</th><td class="warning">{fmt(error_stats.get("runtimeErrorRate", error_stats.get("runtime_error_rate")), '%')}</td></tr>
                    <tr><th>Timeout</th><td>{fmt(error_stats.get("timeoutRate", error_stats.get("timeout_rate")), '%')}</td></tr>
                    <tr><th>Assertion Error</th><td>{fmt(error_stats.get("assertionErrorRate", error_stats.get("assertion_error_rate")), '%')}</td></tr>
                    <tr><th>Import Error</th><td>{fmt(error_stats.get("importErrorRate", error_stats.get("import_error_rate")), '%')}</td></tr>
                    <tr><th>Memory Error</th><td>{fmt(error_stats.get("memoryErrorRate", error_stats.get("memory_error_rate")), '%')}</td></tr>
                </table>
            </div>
        </div>
        
        <h3>Execution Time Statistics</h3>
        <table>
            <tr>
                <th>Mean Runtime</th><td>{fmt(time_stats.get("meanRuntimeMs", time_stats.get("mean_runtime_ms")), ' ms')}</td>
                <th>P50 Runtime</th><td>{fmt(time_stats.get("p50RuntimeMs", time_stats.get("p50_runtime_ms")), ' ms')}</td>
            </tr>
            <tr>
                <th>P95 Runtime</th><td>{fmt(time_stats.get("p95RuntimeMs", time_stats.get("p95_runtime_ms")), ' ms')}</td>
                <th>Max Runtime</th><td>{fmt(time_stats.get("maxRuntimeMs", time_stats.get("max_runtime_ms")), ' ms')}</td>
            </tr>
        </table>
    </div>

    <!-- Checkpoints -->
    {checkpoints_html}

    <!-- Segment Breakdown by Difficulty/Category -->
    {self._generate_segment_breakdown_html(eval_result)}

    <!-- Failure Case Examples -->
    {self._generate_failure_cases_html(eval_result)}

    <!-- Raw Configuration -->
    <div class="section">
        <h2><span class="icon">📋</span> Raw Configuration Data</h2>
        <details class="raw-data">
            <summary>▶ View Complete Configuration JSON</summary>
            <pre>{json.dumps(self.config, indent=2, ensure_ascii=False)}</pre>
        </details>
        <details class="raw-data">
            <summary>▶ View Experiment Metadata JSON</summary>
            <pre>{json.dumps(self.experiment_meta, indent=2, ensure_ascii=False)}</pre>
        </details>
        <details class="raw-data">
            <summary>▶ View Evaluation Results JSON</summary>
            <pre>{json.dumps(self.eval_result, indent=2, ensure_ascii=False)}</pre>
        </details>
        <details class="raw-data">
            <summary>▶ View LoRA Statistics JSON</summary>
            <pre>{json.dumps(self.lora_stats, indent=2, ensure_ascii=False)}</pre>
        </details>
        <details class="raw-data">
            <summary>▶ View Training Metrics JSON (first 20 entries)</summary>
            <pre>{json.dumps(self.metrics[:20] if len(self.metrics) > 20 else self.metrics, indent=2, ensure_ascii=False)}</pre>
        </details>
    </div>

    <footer>
        <p>Generated by LLM Training Pipeline - Python Report Generator</p>
        <p>{datetime.now().isoformat()} | Run: {run_name}</p>
    </footer>
</div>
</body>
</html>'''
        
        return html
    
    def _generate_segment_breakdown_html(self, eval_result: Dict[str, Any]) -> str:
        """Generate HTML for segment breakdown by difficulty/category"""
        segment_stats = eval_result.get("segmentStats", eval_result.get("segment_stats", {}))
        
        if not segment_stats:
            return ""
        
        by_difficulty = segment_stats.get("byDifficulty", segment_stats.get("by_difficulty", {}))
        by_category = segment_stats.get("byCategory", segment_stats.get("by_category", {}))
        
        if not by_difficulty and not by_category:
            return ""
        
        html = '''
    <div class="section">
        <h2><span class="icon">📊</span> Segment Breakdown (Academic Analysis)</h2>
'''
        
        # By Difficulty table
        if by_difficulty:
            html += '''
        <h3>By Difficulty</h3>
        <table>
            <tr>
                <th>Difficulty</th>
                <th>Count</th>
                <th>Pass@1</th>
                <th>Compile Rate</th>
            </tr>
'''
            for diff, stats in by_difficulty.items():
                count = stats.get("count", 0)
                pass_1 = stats.get("pass_at_1", stats.get("passAt1", 0))
                compile_rate = stats.get("compile_rate", stats.get("compileRate", 0))
                html += f'''
            <tr>
                <td class="highlight">{diff}</td>
                <td>{count}</td>
                <td>{pass_1:.1f}%</td>
                <td>{compile_rate:.1f}%</td>
            </tr>
'''
            html += '''        </table>
'''
        
        # By Category table
        if by_category:
            html += '''
        <h3>By Category</h3>
        <table>
            <tr>
                <th>Category</th>
                <th>Count</th>
                <th>Pass@1</th>
                <th>Compile Rate</th>
            </tr>
'''
            for cat, stats in by_category.items():
                count = stats.get("count", 0)
                pass_1 = stats.get("pass_at_1", stats.get("passAt1", 0))
                compile_rate = stats.get("compile_rate", stats.get("compileRate", 0))
                html += f'''
            <tr>
                <td class="highlight">{cat}</td>
                <td>{count}</td>
                <td>{pass_1:.1f}%</td>
                <td>{compile_rate:.1f}%</td>
            </tr>
'''
            html += '''        </table>
'''
        
        html += '''    </div>
'''
        return html
    
    def _generate_failure_cases_html(self, eval_result: Dict[str, Any]) -> str:
        """Generate HTML for failure case examples"""
        failures = eval_result.get("failures", [])
        sample_results = eval_result.get("sample_results", eval_result.get("sampleResults", []))
        
        # Use failures list if available, or sample_results with non-AC verdict
        cases_to_show = []
        
        if failures:
            cases_to_show = failures[:5]  # Limit to 5 examples
        elif sample_results:
            # Filter to failed cases only
            failed_cases = [s for s in sample_results if s.get("verdict", "") != "AC"]
            cases_to_show = failed_cases[:5]
        
        if not cases_to_show:
            return ""
        
        html = '''
    <div class="section">
        <h2><span class="icon">🔍</span> Failure Case Examples (Debug Analysis)</h2>
        <p style="color: var(--text-secondary); margin-bottom: 20px;">
            Representative failure cases for debugging and analysis. Click to expand details.
        </p>
'''
        
        for i, case in enumerate(cases_to_show):
            task_id = case.get("taskId", case.get("task_id", f"Case {i+1}"))
            error_type = case.get("errorType", case.get("error_type", case.get("verdict", "Unknown")))
            error_msg = case.get("error", case.get("traceback", ""))  # Show full content
            prompt = case.get("prompt", "")  # Show full content
            code = case.get("output", case.get("raw_output", case.get("post_process_output", "")))  # Show full content
            exec_time = case.get("executionTimeMs", case.get("execution_time_ms", 0))
            
            # Determine error badge color
            error_colors = {
                "syntax_error": "error", "CE": "error",
                "runtime_error": "warning", "RE": "warning",
                "timeout": "warning", "TLE": "warning",
                "assertion_error": "", "WA": "",
            }
            badge_class = error_colors.get(error_type, "")
            
            html += f'''
        <details class="raw-data" style="margin-bottom: 12px;">
            <summary>
                <span style="color: var(--accent);">{task_id}</span>
                <span class="{badge_class}" style="margin-left: 12px; padding: 2px 8px; background: var(--bg-tertiary); border-radius: 4px;">
                    {error_type}
                </span>
                <span style="color: var(--text-muted); margin-left: 8px;">{exec_time:.0f}ms</span>
            </summary>
            <div style="margin-top: 12px;">
                <p style="color: var(--text-secondary);"><strong>Prompt:</strong></p>
                <pre style="font-size: 11px; white-space: pre-wrap;">{html.escape(prompt)}</pre>
                
                <p style="color: var(--text-secondary); margin-top: 12px;"><strong>Generated Code:</strong></p>
                <pre style="font-size: 11px; white-space: pre-wrap;">{html.escape(code)}</pre>
                
                <p style="color: var(--error); margin-top: 12px;"><strong>Error:</strong></p>
                <pre style="font-size: 11px; color: var(--error);">{html.escape(error_msg)}</pre>
            </div>
        </details>
'''
        
        html += '''    </div>
'''
        return html


def main():
    parser = argparse.ArgumentParser(
        description="Generate extremely detailed and comprehensive training report",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate report from run directory
  python3 report_generator.py --run-dir ./runs/my-run --output report.html
  
  # Generate report from individual files
  python3 report_generator.py --config config.json --metrics metrics.json --output report.html
  
  # Specify title
  python3 report_generator.py --run-dir ./runs/my-run --title "CodeLlama LoRA Fine-tuning" --output report.html
        """
    )
    
    parser.add_argument("--run-dir", "-d", help="Training run directory path")
    parser.add_argument("--config", "-c", help="Config file path (config.json)")
    parser.add_argument("--metrics", "-m", help="Training metrics file path (metrics.json)")
    parser.add_argument("--eval", "-e", help="Evaluation results file path (eval_result.json)")
    parser.add_argument("--meta", help="Experiment metadata file path (experiment_meta.json)")
    parser.add_argument("--output", "-o", required=True, help="Output file path")
    parser.add_argument("--title", "-t", help="Report title")
    parser.add_argument("--format", "-f", choices=["html", "markdown", "md"], default="html",
                        help="Output format: html or markdown (default: html)")
    
    args = parser.parse_args()
    
    generator = ReportGenerator()
    
    # Load data
    if args.run_dir:
        print(f"Loading data from directory: {args.run_dir}")
        generator.load_from_directory(args.run_dir)
    else:
        print("Loading data from individual files...")
        generator.load_from_files(
            config_path=args.config,
            metrics_path=args.metrics,
            eval_path=args.eval,
            meta_path=args.meta
        )
    
    # Generate report
    output_format = args.format.lower()
    if output_format in ["markdown", "md"]:
        print("Generating Markdown report...")
        content = generator.generate_markdown(title=args.title)
    else:
        print("Generating HTML report...")
        content = generator.generate_html(title=args.title)
    
    # Save report
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
    
    print(f"[OK] Report generated successfully: {output_path}")
    print(f"   File size: {len(content) / 1024:.1f} KB")


if __name__ == "__main__":
    main()
