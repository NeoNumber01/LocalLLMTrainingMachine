#!/usr/bin/env python3
"""
Report Generator - 极其详细丰富完整的训练报告生成器

该脚本可以独立运行，从训练日志、配置文件和评估结果生成完整的 HTML 报告。
报告包含：
- 实验元信息（时间、种子、Git版本）
- 完整的环境版本信息
- 硬件配置详情
- 数据集统计
- 模型架构信息
- 训练超参数（完整列表）
- LoRA 配置详情
- 训练曲线（Loss、Learning Rate）
- 所有检查点信息
- 评估结果（Pass@k、错误分布、执行时间）
- 完整的原始配置 JSON

用法:
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
    """加载 JSON 文件"""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: Failed to load {path}: {e}")
        return {}


def format_number(num: Optional[float]) -> str:
    """格式化大数字为可读形式"""
    if num is None:
        return "N/A"
    # 处理字符串类型的输入
    if isinstance(num, str):
        try:
            num = float(num)
        except (ValueError, TypeError):
            return str(num)  # 无法转换则直接返回原字符串
    if num >= 1_000_000_000:
        return f"{num / 1_000_000_000:.2f}B"
    elif num >= 1_000_000:
        return f"{num / 1_000_000:.2f}M"
    elif num >= 1_000:
        return f"{num / 1_000:.1f}K"
    return str(int(num)) if num == int(num) else f"{num:.2f}"


def format_duration(seconds: Optional[float]) -> str:
    """格式化持续时间"""
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
    """安全获取嵌套字典值"""
    for key in keys:
        if isinstance(data, dict) and key in data:
            data = data[key]
        else:
            return default
    return data if data is not None else default


def uniform_sample_indices(total_count: int, losses: List[float] = None, max_samples: int = 50) -> List[int]:
    """
    统一的采样函数 - 从全部数据点中均匀合理地采样
    
    策略:
    1. 如果数据量 <= max_samples，返回所有索引
    2. 否则使用等间距采样（linspace风格），确保包含首尾
    3. 额外包含 loss 最低点（如果提供了 losses）
    
    Args:
        total_count: 总数据点数
        losses: loss 值列表（可选，用于找到最低点）
        max_samples: 最大采样数量
        
    Returns:
        排序后的采样索引列表
    """
    if total_count == 0:
        return []
    
    if total_count == 1:
        return [0]
    
    # 如果数据量小于等于 max_samples，返回所有索引
    if total_count <= max_samples:
        return list(range(total_count))
    
    # 使用等间距采样（linspace风格）
    # 预留1个位置给最低loss点（如果需要），其余均匀分布
    effective_samples = max_samples - 1 if losses else max_samples
    
    sample_indices = set()
    
    # 等间距采样: 0, step, 2*step, ..., total_count-1
    for i in range(effective_samples):
        # 计算索引：i * (total_count - 1) / (effective_samples - 1)
        # 这确保第一个是 0，最后一个是 total_count - 1
        idx = round(i * (total_count - 1) / (effective_samples - 1))
        sample_indices.add(idx)
    
    # 添加 loss 最低点
    if losses and len(losses) == total_count:
        min_loss = min(losses)
        min_loss_idx = losses.index(min_loss)
        sample_indices.add(min_loss_idx)
    
    # 排序返回
    return sorted(sample_indices)


# ============================================================================
# Data Validator - P0 数据一致性检查
# ============================================================================

class DataValidator:
    """数据验证器 - 检测报告数据中的不一致性"""
    
    def __init__(self):
        self.warnings: List[str] = []
        self.errors: List[str] = []
    
    def validate_dataset_stats(self, dataset_config: Dict[str, Any]) -> None:
        """验证数据集统计一致性"""
        total_samples = dataset_config.get("samples", 0) or 0
        train_samples = dataset_config.get("train_samples", 0) or 0
        val_samples = dataset_config.get("val_samples", 0) or 0
        test_samples = dataset_config.get("test_samples", 0) or 0
        
        # 检查 total_samples < train_samples
        if total_samples < train_samples:
            self.warnings.append(
                f"Dataset stats mismatch: total_samples({total_samples}) < train_samples({train_samples})"
            )
        
        # 检查各子集之和是否合理
        subset_sum = train_samples + val_samples + test_samples
        if total_samples > 0 and subset_sum > 0 and subset_sum > total_samples * 1.1:
            self.warnings.append(
                f"Dataset split mismatch: train+val+test({subset_sum}) > total({total_samples})"
            )
    
    def validate_steps(self, planned_steps: Optional[int], actual_steps: Optional[int], 
                       metrics_count: int) -> None:
        """验证步数一致性 - 不再生成警告，steps 信息已在报告中明确显示"""
        # 步数差异已在 Key Metrics 中展示（Planned/Logged/Effective Steps），无需警告
        pass
    
    def validate_learning_rate(self, config_lr: Optional[str], 
                                initial_lr_from_metrics: Optional[float]) -> None:
        """验证学习率配置一致性 - 不再生成警告，LR 信息已在报告中明确显示"""
        # LR 差异已在 Training Configuration 中展示（Config LR vs Actual Initial LR），无需警告
        pass
    
    def validate_scheduler(self, scheduler_config: str, lr_values: List[float]) -> str:
        """检测实际使用的 scheduler 类型"""
        if len(lr_values) < 3:
            return scheduler_config
        
        # 分析 LR 变化模式
        # Linear: 等差递减
        # Cosine: 先快后慢
        # Constant: 不变
        diffs = [lr_values[i+1] - lr_values[i] for i in range(len(lr_values)-1)]
        
        if all(abs(d) < 1e-10 for d in diffs):
            detected = "constant"
        elif len(diffs) >= 2:
            # 检查是否接近等差
            avg_diff = sum(diffs) / len(diffs)
            variance = sum((d - avg_diff) ** 2 for d in diffs) / len(diffs)
            if variance < 1e-12:  # 非常小的方差 = 线性
                detected = "linear"
            else:
                detected = "cosine"  # 假设其他情况是 cosine
        else:
            detected = scheduler_config
        
        if detected != scheduler_config.lower():
            self.warnings.append(
                f"Scheduler mismatch: config={scheduler_config}, detected={detected}"
            )
        
        return detected
    
    def get_all_warnings(self) -> List[str]:
        """获取所有警告"""
        return self.warnings
    
    def get_all_errors(self) -> List[str]:
        """获取所有错误"""
        return self.errors
    
    def has_issues(self) -> bool:
        """是否有任何问题"""
        return len(self.warnings) > 0 or len(self.errors) > 0


def deduplicate_metrics(metrics: List[Dict[str, Any]], filter_no_lr: bool = True) -> List[Dict[str, Any]]:
    """
    按 global_step 去重 metrics，保留每个 step 的最后一条记录。
    P0-4: 过滤掉无效记录 (loss 为 null/0)。
    P0-FIX: 如果 filter_no_lr=True，过滤掉没有 lr 的异常步骤。
    """
    if not metrics:
        return []
    
    # 按 step 分组，保留最后一条
    step_to_metric = {}
    for m in metrics:
        step = m.get("step")
        if step is not None:
            loss = m.get("loss")
            lr = m.get("lr") or m.get("learning_rate")
            
            # 必须有有效的 loss
            if loss is None or loss <= 0:
                continue
            
            # P0-FIX: 如果设置了过滤，跳过没有 lr 或 lr=0 的 warmup 步骤
            # lr=0 表示还没有真正的参数更新（梯度累积期间）
            if filter_no_lr and (lr is None or lr <= 0):
                continue
                
            step_to_metric[step] = m
    
    # 按 step 排序返回
    return [step_to_metric[s] for s in sorted(step_to_metric.keys())]


def extract_lr_values(metrics: List[Dict[str, Any]]) -> List[float]:
    """从 metrics 中提取学习率值列表"""
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
    P0-FIX: 获取有效的最终 loss（有 lr 的最后一个 step）
    排除训练结束后可能出现的 epoch 平均 loss
    """
    if not metrics:
        return None
    
    # 从后往前找有 lr 的 step
    for m in reversed(metrics):
        loss = m.get("loss")
        lr = m.get("lr") or m.get("learning_rate")
        if loss is not None and loss > 0 and lr is not None:
            return loss
    
    # 如果没有找到有 lr 的 step，使用倒数第二个
    if len(metrics) >= 2:
        loss = metrics[-2].get("loss")
        if loss is not None and loss > 0:
            return loss
    
    # 最后兜底
    return metrics[-1].get("loss") if metrics else None


class ReportGenerator:
    """极其详细丰富完整的报告生成器"""
    
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
        """从运行目录加载所有数据"""
        run_path = Path(run_dir)
        
        # 加载配置
        config_path = run_path / "config.json"
        if config_path.exists():
            self.config = load_json_file(str(config_path))
            
        # 加载训练指标
        metrics_path = run_path / "metrics.json"
        if metrics_path.exists():
            data = load_json_file(str(metrics_path))
            self.metrics = data if isinstance(data, list) else data.get("metrics", [])
            
        # 加载评估结果
        eval_path = run_path / "eval_result.json"
        if eval_path.exists():
            self.eval_result = load_json_file(str(eval_path))
            
        # 加载实验元数据
        meta_path = run_path / "experiment_meta.json"
        if meta_path.exists():
            self.experiment_meta = load_json_file(str(meta_path))
            
        # 加载 LoRA 统计
        lora_path = run_path / "lora_stats.json"
        if lora_path.exists():
            self.lora_stats = load_json_file(str(lora_path))
            
        # 加载检查点信息
        checkpoints_path = run_path / "checkpoints.json"
        if checkpoints_path.exists():
            data = load_json_file(str(checkpoints_path))
            self.checkpoints = data if isinstance(data, list) else data.get("checkpoints", [])
            
        # 加载运行信息
        info_path = run_path / "run_info.json"
        if info_path.exists():
            self.run_info = load_json_file(str(info_path))
            
        # 加载数据质量统计 (P2: Data Quality Analysis)
        quality_stats_path = run_path / "data_quality_stats.json"
        if quality_stats_path.exists():
            self.data_quality_stats = load_json_file(str(quality_stats_path))
            
    def load_from_files(self, config_path: Optional[str] = None, 
                        metrics_path: Optional[str] = None,
                        eval_path: Optional[str] = None,
                        meta_path: Optional[str] = None):
        """从单独的文件加载数据"""
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
        """收集当前系统信息（如果未提供元数据）"""
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
        """生成极其详细丰富完整的 Markdown 报告"""
        
        # =====================================================================
        # P0: 数据预处理 - 去重并过滤无效的 metrics（与 HTML 保持一致）
        # =====================================================================
        deduplicated_metrics = deduplicate_metrics(self.metrics)
        
        # 提取各部分数据
        training_config = self.config.get("training", {})
        lora_config = self.config.get("lora", {})
        model_config = self.config.get("model", {})
        dataset_config = self.config.get("dataset", {})
        
        # =====================================================================
        # P0: 检测运行类型 - 区分训练和评测报告
        # =====================================================================
        run_type = self.run_info.get("type", self.config.get("run_type", ""))
        is_eval_run = run_type == "eval" or self.config.get("evaluator") is not None
        
        # 评测专用配置
        eval_protocol = self.config.get("eval_protocol", {})
        code_quality = self.eval_result.get("codeQuality", self.eval_result.get("code_quality", {}))
        reproducibility = self.config.get("reproducibility", {})
        
        # P0: 对评测报告修正 dataset 统计 - 使用 eval_result 中的真实数据
        if is_eval_run:
            eval_total_problems = (self.eval_result.get("totalProblems") or 
                                   self.eval_result.get("total_problems") or 0)
            eval_total_samples = (self.eval_result.get("totalSamples") or 
                                  self.eval_result.get("total_samples") or 0)
            if eval_total_problems > 0:
                dataset_config["samples"] = eval_total_problems
                dataset_config["eval_problems"] = eval_total_problems
                dataset_config["eval_samples"] = eval_total_samples
        
        # 系统信息（空字典也视为无数据）
        system_info = self.experiment_meta if self.experiment_meta else self.collect_system_info()
        
        # 运行信息
        run_name = title or self.run_info.get("name", self.config.get("run_name", "Training Run"))
        run_id = self.run_info.get("id", "N/A")
        duration = self.run_info.get("duration", "")
        seed = self.config.get("seed", training_config.get("seed", "N/A"))
        git_commit = self.run_info.get("git_commit", "N/A")
        
        # =====================================================================
        # 训练步数统计 - 区分三种不同概念的 steps
        # =====================================================================
        # 1. Planned steps: 配置中计划的步数
        planned_steps = training_config.get("total_steps") or training_config.get("planned_steps")
        
        # 2. Raw logged steps: 原始日志中记录的总步数（包含 warmup/pre-log）
        # 优先使用从 Node.js 传入的值
        raw_logged_steps_from_config = training_config.get("raw_logged_steps")
        raw_logged_steps = raw_logged_steps_from_config if raw_logged_steps_from_config else (len(self.metrics) if self.metrics else 0)
        
        # 3. Effective update steps: 真正发生参数更新的步数
        # 使用 Python 端过滤后的 deduplicated_metrics 的实际长度（最准确）
        effective_steps = len(deduplicated_metrics) if deduplicated_metrics else 0
        
        # 用于显示的 total_steps（优先使用 effective_steps）
        total_steps = effective_steps if effective_steps > 0 else (planned_steps or "N/A")
        
        # P0-FIX: 获取有效的 final_loss（有 lr 的最后一个 step）
        final_loss = get_valid_final_loss(deduplicated_metrics) if deduplicated_metrics else None
        
        # 计算 warmup 步骤数（原始日志 - 有效步骤）
        warmup_steps = raw_logged_steps - effective_steps if raw_logged_steps > effective_steps else 0
        
        # 获取第一个和最后一个有效步骤的 step 号（用于 Note 显示）
        first_effective_step = deduplicated_metrics[0].get("step", 1) if deduplicated_metrics else 1
        last_effective_step = deduplicated_metrics[-1].get("step", effective_steps) if deduplicated_metrics else effective_steps
        
        # LoRA 统计
        lora_stats = self.lora_stats or {}
        trainable_params = lora_stats.get("trainable_params")
        total_params = lora_stats.get("total_params")
        trainable_percent = lora_stats.get("trainable_percent")
        
        # 评估结果
        eval_result = self.eval_result or {}
        pass_at_1 = eval_result.get("pass_at_1") or eval_result.get("passAt1")
        pass_at_5 = get_value(eval_result, "pass_at_k", "5") or get_value(eval_result, "passAtK", "5")
        pass_at_10 = get_value(eval_result, "pass_at_k", "10") or get_value(eval_result, "passAtK", "10")
        compile_rate = eval_result.get("compile_rate") or eval_result.get("compileRate")
        
        error_stats = eval_result.get("error_stats", eval_result.get("errorStats", {}))
        time_stats = eval_result.get("time_stats", eval_result.get("timeStats", {}))
        
        # 格式化函数
        def fmt(val, suffix="", decimals=2):
            if val is None:
                return "N/A"
            try:
                return f"{float(val):.{decimals}f}{suffix}"
            except:
                return str(val)
        
        def fmt_na(val):
            return str(val) if val is not None else "N/A"
        
        # 生成 Markdown
        md_lines = []
        
        # 标题
        md_lines.append(f"# {run_name}")
        md_lines.append("")
        # P0: 区分报告类型标题
        report_type_label = "Evaluation Report" if is_eval_run else "Training Report"
        md_lines.append(f"> {report_type_label} | Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        md_lines.append("")
        
        # 概览
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
        
        # 关键指标
        md_lines.append("## Key Metrics")
        md_lines.append("")
        md_lines.append("| Metric | Value |")
        md_lines.append("|--------|-------|")
        md_lines.append(f"| **Pass@1** | {fmt(pass_at_1, '%')} |")
        md_lines.append(f"| Compile Rate | {fmt(compile_rate, '%')} |")
        
        # P0: 评测报告不显示训练相关指标
        if not is_eval_run:
            md_lines.append(f"| Final Loss | {fmt(final_loss, '', 4) if final_loss else 'N/A'} |")
            
            # 显示三种 steps（如果有差异）
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
            # P0: 评测报告显示评测相关统计
            eval_total_problems = dataset_config.get('eval_problems', 0)
            eval_total_samples = dataset_config.get('eval_samples', 0)
            md_lines.append(f"| Total Problems (N_tasks) | {eval_total_problems} |")
            md_lines.append(f"| Total Samples (N x k) | {eval_total_samples} |")
            if eval_total_problems < 30:
                md_lines.append(f"| Sample Size Warning | N_tasks={eval_total_problems} is small |")
        md_lines.append("")
        
        # P0: 添加步数差异说明（仅训练报告，评测报告不显示）
        if not is_eval_run and warmup_steps > 0:
            md_lines.append(f"> **Note:** Steps 1-{first_effective_step - 1} are pre-update logs during warmup/gradient accumulation (lr=0). Effective parameter updates: {effective_steps} steps (Steps {first_effective_step}-{last_effective_step}).")
            md_lines.append("")
        
        # 模型信息
        md_lines.append("## Model")
        md_lines.append("")
        md_lines.append("| Property | Value |")
        md_lines.append("|----------|-------|")
        md_lines.append(f"| Model Name | {fmt_na(model_config.get('name', self.config.get('model_name')))} |")
        md_lines.append(f"| Model Path | {fmt_na(model_config.get('path', self.config.get('model_path')))} |")
        md_lines.append(f"| Parameters | {fmt_na(model_config.get('params'))} |")
        md_lines.append(f"| Quantization | {fmt_na(lora_config.get('quantization', 'None'))} |")
        md_lines.append("")
        
        # 数据集信息
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
        
        # P0: 训练配置 (仅训练报告，评测报告跳过)
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
            # P0-FIX: 区分 Config LR vs Actual Initial LR
            config_lr = training_config.get('lr', training_config.get('learning_rate', 'N/A'))
            # 从 metrics 的第一步获取实际初始 LR
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
            
            # LoRA 配置
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
        # P1: Evaluation Protocol (仅评测报告)
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
            
            # 可复现性信息
            md_lines.append("### Reproducibility")
            md_lines.append("")
            md_lines.append("| Parameter | Value |")
            md_lines.append("|-----------|-------|")
            md_lines.append(f"| Seed | {seed} |")
            md_lines.append(f"| Git Commit | {git_commit if git_commit != 'N/A' else 'Not recorded'} |")
            md_lines.append(f"| Evaluator Version | {reproducibility.get('evaluator_version', '1.0.0')} |")
            md_lines.append("")
        
        # 评估结果
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
        
        # 环境信息
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
        
        # 硬件信息
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
        # P2: Code Quality Metrics (仅评测报告)
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
            
            # P0-FIX: Extra I/O 详细解释
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
        # P0: 仅在训练报告中显示，评测报告跳过
        # =====================================================================
        if not is_eval_run and deduplicated_metrics:
            md_lines.append("## Training Results")
            md_lines.append("")
            
            # 5.0 Per-Epoch Metrics (kabul-main style)
            # Group metrics by epoch
            # P0-FIX: HuggingFace Trainer 的 epoch 是小数形式（如 0.1, 0.2...），需要取整后分组
            epochs_data = {}
            for m in deduplicated_metrics:
                raw_epoch = m.get("epoch")
                # 如果没有 epoch 字段，默认为 1
                if raw_epoch is None:
                    epoch = 1
                else:
                    # 取整：0.1->1, 0.9->1, 1.0->1, 1.1->2
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
            
            # 计算关键统计（使用过滤后的 metrics）
            losses = [m.get("loss") for m in deduplicated_metrics if m.get("loss") is not None]
            lr_values = [m.get("lr") or m.get("learning_rate") for m in deduplicated_metrics if m.get("lr") or m.get("learning_rate")]
            
            if losses:
                initial_loss = losses[0]
                # 获取第一个有效步骤的 step 号（用于显示）
                first_effective_step = deduplicated_metrics[0].get("step", 1) if deduplicated_metrics else 1
                # P0-FIX: 使用有效的 final_loss（有 lr 的最后一步）
                final_loss_val = get_valid_final_loss(deduplicated_metrics)
                if final_loss_val is None:
                    final_loss_val = losses[-1]  # fallback
                # 获取最后一个有效步骤的 step 号
                last_effective_step = deduplicated_metrics[-1].get("step", len(deduplicated_metrics)) if deduplicated_metrics else len(losses)
                min_loss = min(losses)
                max_loss = max(losses)
                avg_loss = sum(losses) / len(losses)
                loss_reduction = ((initial_loss - final_loss_val) / initial_loss * 100) if initial_loss > 0 else 0
                
                # 找到收敛点 (loss 首次低于 0.1)
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
                # 使用科研风格标签：显示第一个有效更新步骤号
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
                # 添加 Final Loss 定义说明
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
                    # 添加 cosine scheduler 短步数说明
                    if scheduler_type.lower() == 'cosine' and len(deduplicated_metrics) <= 20:
                        md_lines.append("> **Note:** Due to the small number of training steps, the cosine schedule appears approximately linear.")
                        md_lines.append("")
                
                # 5.3 Loss Curve Sample Points
                md_lines.append("### Loss Curve Sample Points")
                md_lines.append("")
                md_lines.append("| Step | Loss | Learning Rate |")
                md_lines.append("|------|------|--------------|")
                
                # 使用统一采样函数获取索引（从过滤后的 metrics）
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
        
        # 原始配置
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
        
        # 页脚
        md_lines.append("---")
        md_lines.append("")
        md_lines.append(f"*Report generated by LLMTrainPipeline | {datetime.now().isoformat()}*")
        
        return "\n".join(md_lines)
    
    def generate_loss_curve_svg(self, width: int = 800, height: int = 250) -> str:
        """生成训练曲线 SVG"""
        if not self.metrics:
            return '<p style="color: #707080; text-align: center; padding: 40px;">No training data available</p>'
        
        padding = {"top": 30, "right": 50, "bottom": 50, "left": 70}
        chart_width = width - padding["left"] - padding["right"]
        chart_height = height - padding["top"] - padding["bottom"]
        
        # 提取数据
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
        
        # 生成路径
        path_points = []
        for i, (step, loss) in enumerate(zip(steps, losses)):
            x, y = scale_x(step), scale_y(loss)
            cmd = "M" if i == 0 else "L"
            path_points.append(f"{cmd} {x:.1f} {y:.1f}")
        path_data = " ".join(path_points)
        
        # Y 轴刻度
        y_ticks = []
        for t in [0, 0.25, 0.5, 0.75, 1.0]:
            val = min_loss + t * (max_loss - min_loss)
            y = scale_y(val)
            y_ticks.append(f'<line x1="{padding["left"]}" y1="{y:.1f}" x2="{width - padding["right"]}" y2="{y:.1f}" stroke="#3a3a5a" stroke-dasharray="4"/>')
            y_ticks.append(f'<text x="{padding["left"] - 10}" y="{y + 4:.1f}" text-anchor="end" fill="#a0a0b0" font-size="12">{val:.3f}</text>')
        
        # X 轴刻度
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
        """生成详细的 Loss 数据表格 HTML"""
        if not metrics:
            return ''
        
        # 统计信息
        total_points = len(metrics)
        losses = [m.get("loss", 0) for m in metrics if m.get("loss") is not None]
        
        min_loss = min(losses) if losses else None
        max_loss = max(losses) if losses else None
        avg_loss = sum(losses) / len(losses) if losses else None
        
        # =====================================================================
        # 计算 Per-Epoch 统计信息
        # P0-FIX: HuggingFace Trainer 的 epoch 是小数形式（如 0.1, 0.2...），需要取整后分组
        # =====================================================================
        epochs_data = {}
        for m in metrics:
            raw_epoch = m.get("epoch")
            # 如果没有 epoch 字段，默认为 1
            if raw_epoch is None:
                epoch = 1
            else:
                # 取整：0.1->1, 0.9->1, 1.0->1, 1.1->2（ceiling 逻辑）
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
        
        # 生成 Per-Epoch 表格行
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
        
        # Per-Epoch HTML 部分（当有多个 epoch 或用户可能关心时显示）
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
        
        # 找到最低 loss 对应的 step
        min_loss_step = None
        for m in metrics:
            if m.get("loss") == min_loss:
                min_loss_step = m.get("step")
                break
        
        # 生成摘要表格（显示关键点：开始、结束、最低点 + 均匀采样）
        summary_rows = []
        
        # 使用统一采样函数获取索引
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
        
        # 生成完整数据的可展开表格
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
            
            <!-- 统计摘要 -->
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
            
            <!-- Per-Epoch 统计表格 -->
            {per_epoch_html}
            
            <!-- 摘要表格 -->
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
            
            <!-- 完整数据（可展开） -->
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
        """生成极其详细丰富完整的 HTML 报告"""
        
        # =====================================================================
        # P0: 数据预处理 - 去重 metrics
        # =====================================================================
        deduplicated_metrics = deduplicate_metrics(self.metrics)
        
        # 提取各部分数据
        training_config = self.config.get("training", {})
        lora_config = self.config.get("lora", {})
        model_config = self.config.get("model", {})
        dataset_config = self.config.get("dataset", {})
        
        # =====================================================================
        # P0-1: 自动修正 dataset 统计 - total_samples 不能小于 train_samples
        # =====================================================================
        total_samples = dataset_config.get("samples", 0) or 0
        train_samples = dataset_config.get("train_samples", 0) or 0
        if total_samples < train_samples:
            # 自动修正：使用 train_samples 作为 total
            dataset_config["samples"] = train_samples
        elif total_samples == 0 and train_samples > 0:
            dataset_config["samples"] = train_samples
        
        # 系统信息（优先使用记录的，否则收集当前）
        # 注意：空字典 {} 也视为无数据，需要收集当前系统信息
        system_info = self.experiment_meta if self.experiment_meta else self.collect_system_info()
        
        # 运行信息
        run_name = title or self.run_info.get("name", self.config.get("run_name", "Training Run"))
        run_id = self.run_info.get("id", "N/A")
        start_time = self.run_info.get("start_time", self.config.get("start_time", ""))
        end_time = self.run_info.get("end_time", self.config.get("end_time", ""))
        duration = self.run_info.get("duration", "")
        seed = self.config.get("seed", training_config.get("seed", "N/A"))
        git_commit = self.run_info.get("git_commit", "N/A")
        
        # =====================================================================
        # P0: 训练步数统计 - 区分三种不同概念的 steps（与 Markdown 报告保持一致）
        # =====================================================================
        # 1. Planned steps: 配置中计划的步数
        planned_steps = training_config.get("total_steps") or training_config.get("planned_steps")
        
        # 2. Raw logged steps: 原始日志中记录的总步数（包含 warmup/pre-log）
        # 优先使用从 Node.js 传入的值
        raw_logged_steps_from_config = training_config.get("raw_logged_steps")
        raw_logged_steps = raw_logged_steps_from_config if raw_logged_steps_from_config else (len(self.metrics) if self.metrics else 0)
        
        # 3. Effective update steps: 真正发生参数更新的步数
        # 使用 Python 端过滤后的 deduplicated_metrics 的实际长度（最准确）
        effective_steps = len(deduplicated_metrics) if deduplicated_metrics else 0
        
        # 用于显示的 total_steps（优先使用 effective_steps）
        total_steps = effective_steps if effective_steps > 0 else (planned_steps or "N/A")
        
        # 计算 warmup 步骤数（原始日志 - 有效步骤）
        warmup_steps = raw_logged_steps - effective_steps if raw_logged_steps > effective_steps else 0
        
        # =====================================================================
        # P1-2: Final Loss - 取最后一个有效的 train_step loss（非 summary）
        # =====================================================================
        final_loss = None
        if deduplicated_metrics:
            # P0-FIX: 优先找有 lr 的最后一个 step（排除 epoch 平均 loss）
            for m in reversed(deduplicated_metrics):
                loss = m.get("loss")
                lr = m.get("lr") or m.get("learning_rate")
                if loss is not None and loss > 0 and lr is not None:
                    final_loss = loss
                    break
            
            # 如果没有找到有 lr 的 step，使用倒数第二个（避免使用可能的 epoch 平均值）
            if final_loss is None and len(deduplicated_metrics) >= 2:
                final_loss = deduplicated_metrics[-2].get("loss")
            
            # 最后兜底
            if final_loss is None and deduplicated_metrics:
                final_loss = deduplicated_metrics[-1].get("loss")
        
        # 获取第一个和最后一个有效步骤的 step 号（用于显示）
        first_effective_step = deduplicated_metrics[0].get("step", 1) if deduplicated_metrics else 1
        last_effective_step = deduplicated_metrics[-1].get("step", effective_steps) if deduplicated_metrics else effective_steps
        
        # LoRA 统计
        lora_stats = self.lora_stats or {}
        trainable_params = lora_stats.get("trainable_params")
        total_params = lora_stats.get("total_params")
        trainable_percent = lora_stats.get("trainable_percent")
        
        # 评估结果
        eval_result = self.eval_result or {}
        pass_at_1 = eval_result.get("pass_at_1") or eval_result.get("passAt1")
        pass_at_5 = get_value(eval_result, "pass_at_k", "5") or get_value(eval_result, "passAtK", "5")
        pass_at_10 = get_value(eval_result, "pass_at_k", "10") or get_value(eval_result, "passAtK", "10")
        compile_rate = eval_result.get("compile_rate") or eval_result.get("compileRate")
        
        error_stats = eval_result.get("error_stats", eval_result.get("errorStats", {}))
        time_stats = eval_result.get("time_stats", eval_result.get("timeStats", {}))
        
        # =====================================================================
        # P0: 数据验证
        # =====================================================================
        validator = DataValidator()
        
        # 验证 dataset 统计
        validator.validate_dataset_stats(dataset_config)
        
        # 验证步数
        validator.validate_steps(planned_steps, effective_steps, len(deduplicated_metrics))
        
        # 验证学习率
        config_lr = training_config.get("lr") or training_config.get("learning_rate")
        lr_values = extract_lr_values(deduplicated_metrics)
        initial_lr = lr_values[0] if lr_values else None
        validator.validate_learning_rate(str(config_lr) if config_lr else None, initial_lr)
        
        # 验证 scheduler
        scheduler_config = training_config.get("scheduler", "cosine")
        detected_scheduler = validator.validate_scheduler(scheduler_config, lr_values)
        
        # 收集所有警告
        validation_warnings = validator.get_all_warnings()
        
        # 格式化函数
        def fmt(val, suffix="", decimals=2):
            if val is None:
                return "N/A"
            try:
                return f"{float(val):.{decimals}f}{suffix}"
            except:
                return str(val)
        
        def fmt_na(val):
            return str(val) if val is not None else '<span class="muted">Not collected</span>'
        
        # 生成训练曲线 - 使用去重后的 metrics
        # 临时替换 self.metrics 以生成曲线
        original_metrics = self.metrics
        self.metrics = deduplicated_metrics
        loss_curve_svg = self.generate_loss_curve_svg()
        self.metrics = original_metrics
        
        # =====================================================================
        # 生成详细的 Loss 数据表格
        # =====================================================================
        loss_table_html = self.generate_loss_table_html(deduplicated_metrics)
        
        # 生成检查点列表
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
        # P0: 生成警告横幅 HTML
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
        # P0: 评测状态显示
        # =====================================================================
        eval_not_run = not self.eval_result or (pass_at_1 is None and compile_rate is None)
        eval_status_msg = ""
        if eval_not_run:
            eval_status_msg = '<div class="eval-not-run">📋 Evaluation Not Run - 未运行代码评测，Pass@k 和 Compile Rate 等指标无数据</div>'
        
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
            error_msg = case.get("error", case.get("traceback", ""))  # 完整显示
            prompt = case.get("prompt", "")  # 完整显示
            code = case.get("output", case.get("raw_output", case.get("post_process_output", "")))  # 完整显示
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
        description="生成极其详细丰富完整的训练报告",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 从运行目录生成报告
  python3 report_generator.py --run-dir ./runs/my-run --output report.html
  
  # 从单独的文件生成报告
  python3 report_generator.py --config config.json --metrics metrics.json --output report.html
  
  # 指定标题
  python3 report_generator.py --run-dir ./runs/my-run --title "CodeLlama LoRA Fine-tuning" --output report.html
        """
    )
    
    parser.add_argument("--run-dir", "-d", help="训练运行目录路径")
    parser.add_argument("--config", "-c", help="配置文件路径 (config.json)")
    parser.add_argument("--metrics", "-m", help="训练指标文件路径 (metrics.json)")
    parser.add_argument("--eval", "-e", help="评估结果文件路径 (eval_result.json)")
    parser.add_argument("--meta", help="实验元数据文件路径 (experiment_meta.json)")
    parser.add_argument("--output", "-o", required=True, help="输出文件路径")
    parser.add_argument("--title", "-t", help="报告标题")
    parser.add_argument("--format", "-f", choices=["html", "markdown", "md"], default="html",
                        help="输出格式: html 或 markdown (默认: html)")
    
    args = parser.parse_args()
    
    generator = ReportGenerator()
    
    # 加载数据
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
    
    # 生成报告
    output_format = args.format.lower()
    if output_format in ["markdown", "md"]:
        print("Generating Markdown report...")
        content = generator.generate_markdown(title=args.title)
    else:
        print("Generating HTML report...")
        content = generator.generate_html(title=args.title)
    
    # 保存报告
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
    
    print(f"[OK] Report generated successfully: {output_path}")
    print(f"   File size: {len(content) / 1024:.1f} KB")


if __name__ == "__main__":
    main()
