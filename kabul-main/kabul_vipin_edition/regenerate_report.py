"""
Enhanced Training Report Generator
Regenerates a comprehensive training report from existing training_logs.json
"""
import json
import os
from datetime import datetime, timedelta
from train_config import TrainingConfig

def regenerate_report():
    config = TrainingConfig()
    logs_path = os.path.join(config.output_dir, "training_logs.json")
    report_path = os.path.join(config.output_dir, "train_report.md")
    
    if not os.path.exists(logs_path):
        print(f"Error: {logs_path} not found!")
        return
    
    with open(logs_path, 'r', encoding='utf-8') as f:
        history = json.load(f)
    
    # Load data quality stats if available
    quality_stats_path = os.path.join(config.output_dir, "data_quality_stats.json")
    if os.path.exists(quality_stats_path):
        with open(quality_stats_path, 'r', encoding='utf-8') as f:
            quality_stats = json.load(f)
    else:
        quality_stats = None
        print(f"Warning: {quality_stats_path} not found. Run analyze_data_quality.py first for detailed stats.")
    
    # Load inference benchmark stats if available
    inference_path = os.path.join(config.output_dir, "inference_benchmark.json")
    if os.path.exists(inference_path):
        with open(inference_path, 'r', encoding='utf-8') as f:
            inference_stats = json.load(f)
    else:
        inference_stats = None
        print(f"Warning: {inference_path} not found. Run benchmark_inference.py first for inference metrics.")

    
    # ============ Extract all data ============
    epochs_data = history.get("epochs", [])
    data_stats = history.get("data_stats", {})
    model_info = history.get("model_info", {})
    system_info = history.get("system_info", {})
    
    # Calculate aggregated metrics
    best_eval_loss = min([e["eval_loss"] for e in epochs_data]) if epochs_data else "N/A"
    total_duration_seconds = sum([e["duration_seconds"] for e in epochs_data]) if epochs_data else 0
    total_duration_str = str(timedelta(seconds=int(total_duration_seconds)))
    
    # Get all step data for loss curve analysis
    all_steps = []
    for epoch in epochs_data:
        for step in epoch.get("step_data", []):
            all_steps.append(step)
    
    # Loss statistics
    if all_steps:
        all_losses = [s["loss"] for s in all_steps]
        min_loss = min(all_losses)
        max_loss = max(all_losses)
        avg_loss = sum(all_losses) / len(all_losses)
        
        # Get actual training steps (not log entry count)
        actual_total_steps = all_steps[-1]["step"]  # Last step number
        first_step = all_steps[0]["step"]
        logging_interval = all_steps[1]["step"] - all_steps[0]["step"] if len(all_steps) > 1 else 10
        steps_per_epoch = actual_total_steps // len(epochs_data) if epochs_data else 0
        
        # Find convergence point (first time loss drops below 0.1)
        convergence_step = None
        for s in all_steps:
            if s["loss"] < 0.1:
                convergence_step = s["step"]
                break
        
        # Learning rate range
        all_lrs = [s["lr"] for s in all_steps]
        max_lr = max(all_lrs)
        min_lr = min(all_lrs)
        
        # Sample some key points for loss curve
        total_log_entries = len(all_steps)
        sample_indices = [0, total_log_entries//4, total_log_entries//2, 3*total_log_entries//4, total_log_entries-1]
        sampled_steps = [all_steps[i] for i in sample_indices if i < total_log_entries]
    else:
        min_loss = max_loss = avg_loss = "N/A"
        convergence_step = None
        max_lr = min_lr = "N/A"
        sampled_steps = []
        actual_total_steps = 0
        logging_interval = 10
        steps_per_epoch = 0

    
    # Pre-compute formatted values
    initial_loss = f"{epochs_data[0]['avg_train_loss']:.4f}" if epochs_data else 'N/A'
    final_loss = f"{epochs_data[-1]['avg_train_loss']:.4f}" if epochs_data else 'N/A'
    
    # Pre-format all conditional values to avoid f-string issues
    best_eval_loss_str = f"{best_eval_loss:.6f}" if isinstance(best_eval_loss, float) else str(best_eval_loss)
    min_loss_str = f"{min_loss:.4f}" if isinstance(min_loss, float) else str(min_loss)
    max_loss_str = f"{max_loss:.4f}" if isinstance(max_loss, float) else str(max_loss)
    avg_loss_str = f"{avg_loss:.4f}" if isinstance(avg_loss, float) else str(avg_loss)
    max_lr_str = f"{max_lr:.2e}" if isinstance(max_lr, float) else str(max_lr)
    min_lr_str = f"{min_lr:.2e}" if isinstance(min_lr, float) else str(min_lr)
    
    # Loss reduction percentage
    if epochs_data and len(epochs_data) >= 2:
        loss_reduction = ((epochs_data[0]['avg_train_loss'] - epochs_data[-1]['avg_train_loss']) / epochs_data[0]['avg_train_loss']) * 100
        loss_reduction_str = f"{loss_reduction:.1f}%"
    else:
        loss_reduction_str = "N/A"

    
    # ============ Generate Markdown Report ============
    md = f"""# CodeT5 Java to C# Translation - Training Report

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**Total Training Duration:** {total_duration_str}  
**Best Validation Loss:** {best_eval_loss_str}

---

## 1. Executive Summary

| Metric | Value |
|--------|-------|
| Total Training Time | {total_duration_str} |
| Training Samples | {data_stats.get('train_samples', 'N/A'):,} |
| Validation Samples | {data_stats.get('valid_samples', 'N/A'):,} |
| Total Training Steps | {actual_total_steps:,} |
| Initial Train Loss | {initial_loss} |
| Final Train Loss | {final_loss} |
| Loss Reduction | {loss_reduction_str} |
| Best Eval Loss | {best_eval_loss_str} |

---

## 2. System Environment

| Component | Details |
|-----------|---------|
| **Hardware** | |
| GPU | {system_info.get('gpu_name', 'N/A')} |
| GPU Count | {system_info.get('gpu_count', 'N/A')} |
| VRAM | {system_info.get('gpu_memory_gb', 'N/A')} GB |
| CUDA Version | {system_info.get('cuda_version', 'N/A')} |
| CPU | {system_info.get('cpu', 'N/A')} |
| RAM | {system_info.get('ram_gb', 'N/A')} GB |
| **Software** | |
| OS | {system_info.get('os', 'N/A')} |
| Python | {system_info.get('python_version', 'N/A')} |
| PyTorch | {system_info.get('pytorch_version', 'N/A')} |
| Transformers | {system_info.get('transformers_version', 'N/A')} |

---

## 3. Dataset Statistics
"""
    
    # Add data quality stats if available
    if quality_stats:
        dedup = quality_stats.get("dedup_stats", {})
        raw = quality_stats.get("raw_counts", {})
        token = quality_stats.get("token_stats", {})
        leakage = quality_stats.get("leakage_stats", {})
        
        train_dedup = dedup.get("train", {})
        valid_dedup = dedup.get("valid", {})
        train_token = token.get("train", {})
        valid_token = token.get("valid", {})
        
        md += f"""
### 3.1 Raw Data & Deduplication

| Metric | Training Set | Validation Set |
|--------|-------------|----------------|
| Raw Java Samples | {raw.get('java_train', 'N/A'):,} | {raw.get('java_valid', 'N/A'):,} |
| Raw C# Samples | {raw.get('csharp_train', 'N/A'):,} | {raw.get('csharp_valid', 'N/A'):,} |
| Aligned Pairs (before dedup) | {train_dedup.get('before', 'N/A'):,} | {valid_dedup.get('before', 'N/A'):,} |
| **Final Pairs (after dedup)** | **{train_dedup.get('after', 'N/A'):,}** | **{valid_dedup.get('after', 'N/A'):,}** |
| Duplicates Removed | {train_dedup.get('removed', 'N/A'):,} | {valid_dedup.get('removed', 'N/A'):,} |
| Deduplication Rate | {train_dedup.get('rate', 0):.2f}% | {valid_dedup.get('rate', 0):.2f}% |

### 3.2 Token Length Distribution

| Language | Mean | Median (P50) | P95 | Max |
|----------|------|--------------|-----|-----|
| Java (Train) | {train_token.get('java_stats', {}).get('mean', 0):.1f} | {train_token.get('java_stats', {}).get('p50', 0)} | {train_token.get('java_stats', {}).get('p95', 0)} | {train_token.get('java_stats', {}).get('max', 0)} |
| C# (Train) | {train_token.get('csharp_stats', {}).get('mean', 0):.1f} | {train_token.get('csharp_stats', {}).get('p50', 0)} | {train_token.get('csharp_stats', {}).get('p95', 0)} | {train_token.get('csharp_stats', {}).get('max', 0)} |
| Java (Valid) | {valid_token.get('java_stats', {}).get('mean', 0):.1f} | {valid_token.get('java_stats', {}).get('p50', 0)} | {valid_token.get('java_stats', {}).get('p95', 0)} | {valid_token.get('java_stats', {}).get('max', 0)} |
| C# (Valid) | {valid_token.get('csharp_stats', {}).get('mean', 0):.1f} | {valid_token.get('csharp_stats', {}).get('p50', 0)} | {valid_token.get('csharp_stats', {}).get('p95', 0)} | {valid_token.get('csharp_stats', {}).get('max', 0)} |

### 3.3 Truncation & Data Quality

| Metric | Training Set | Validation Set |
|--------|-------------|----------------|
| Max Sequence Length | {quality_stats.get('max_length', 512)} | {quality_stats.get('max_length', 512)} |
| Java Truncation Rate | {train_token.get('truncated_java_rate', 0):.2f}% | {valid_token.get('truncated_java_rate', 0):.2f}% |
| C# Truncation Rate | {train_token.get('truncated_csharp_rate', 0):.2f}% | {valid_token.get('truncated_csharp_rate', 0):.2f}% |
| Empty Samples | {train_token.get('empty_java', 0) + train_token.get('empty_csharp', 0)} | {valid_token.get('empty_java', 0) + valid_token.get('empty_csharp', 0)} |
| Very Short Samples (<10 tokens) | {train_token.get('short_samples', 0)} ({train_token.get('short_rate', 0):.2f}%) | {valid_token.get('short_samples', 0)} ({valid_token.get('short_rate', 0):.2f}%) |

### 3.4 Train-Valid Leakage Check (Enhanced)

| Detection Method | Java | C# |
|-----------------|------|-----|
| Exact Match | {leakage.get('exact_match', {}).get('java', leakage.get('java_exact_match', 0))} ({leakage.get('exact_match', {}).get('java_rate', leakage.get('java_leakage_rate', 0)):.2f}%) | {leakage.get('exact_match', {}).get('csharp', leakage.get('csharp_exact_match', 0))} ({leakage.get('exact_match', {}).get('csharp_rate', leakage.get('csharp_leakage_rate', 0)):.2f}%) |
| Normalized Match (no whitespace/comments) | {leakage.get('normalized_match', {}).get('java', 0)} ({leakage.get('normalized_match', {}).get('java_rate', 0):.2f}%) | {leakage.get('normalized_match', {}).get('csharp', 0)} ({leakage.get('normalized_match', {}).get('csharp_rate', 0):.2f}%) |
| High Similarity (Jaccard >{leakage.get('high_similarity', {}).get('threshold', 0.8)}) | {leakage.get('high_similarity', {}).get('java', 0)} ({leakage.get('high_similarity', {}).get('java_rate', 0):.2f}%) | {leakage.get('high_similarity', {}).get('csharp', 0)} ({leakage.get('high_similarity', {}).get('csharp_rate', 0):.2f}%) |

**Leakage Assessment:** {'✅ Clean - No significant leakage detected' if leakage.get('high_similarity', {}).get('java_rate', 0) < 1 and leakage.get('normalized_match', {}).get('java_rate', 0) < 1 else '⚠️ Potential leakage detected'}

"""
    else:
        md += f"""
| Metric | Training Set | Validation Set |
|--------|-------------|----------------|
| Samples (after dedup) | {data_stats.get('train_samples', 'N/A'):,} | {data_stats.get('valid_samples', 'N/A'):,} |

> **Note:** Run `python analyze_data_quality.py` to generate detailed token statistics and leakage analysis.

"""
    
    md += f"""**Data Source:**
- Java Training: `{config.java_train_path}`
- C# Training: `{config.csharp_train_path}`
- Java Validation: `{config.java_valid_path}`
- C# Validation: `{config.csharp_valid_path}`


---

## 4. Model Configuration

### 4.1 Base Model Architecture
| Parameter | Value |
|-----------|-------|
| Model Name | `{config.base_model}` |
| Architecture | Encoder-Decoder (T5-based) |
| Total Parameters | {model_info.get('total_parameters', 'N/A'):,} |
| Trainable Parameters | {model_info.get('trainable_parameters', 'N/A'):,} |
| Frozen Parameters | {model_info.get('frozen_parameters', 0):,} |
| Model Size | {model_info.get('model_size_mb', 'N/A')} MB |

### 4.2 Training Hyperparameters
| Parameter | Value | Description |
|-----------|-------|-------------|
| Learning Rate | {config.learning_rate} | Peak learning rate |
| Batch Size (per device) | {config.per_device_train_batch_size} | Samples per GPU |
| Gradient Accumulation | {config.gradient_accumulation_steps} | Steps to accumulate |
| **Effective Batch Size** | **{config.per_device_train_batch_size * config.gradient_accumulation_steps}** | Total samples per update |
| Epochs | {config.num_train_epochs} | Training iterations |
| Weight Decay | {config.weight_decay} | L2 regularization |
| Warmup Steps | {config.warmup_steps} | LR warmup period |
| Max Sequence Length | {config.max_length} | Token limit |
| Mixed Precision (FP16) | {'Enabled' if config.fp16 else 'Disabled'} | Memory optimization |
| Logging Steps | {config.logging_steps} | Log frequency |
| Save Strategy | {config.save_strategy} | Checkpoint strategy |

---

## 5. Training Results

### 5.1 Per-Epoch Metrics

| Epoch | Train Loss | Eval Loss | Duration | Eval Throughput |
|-------|------------|-----------|----------|-----------------|
"""
    
    for e in epochs_data:
        eval_throughput = f"{e.get('eval_samples_per_second', 0):.1f} samples/s" if 'eval_samples_per_second' in e else 'N/A'
        duration_mins = e['duration_seconds'] / 60
        md += f"| {int(e['epoch'])} | {e['avg_train_loss']:.4f} | {e['eval_loss']:.4f} | {duration_mins:.1f} min | {eval_throughput} |\n"
    
    md += f"""
### 5.2 Training Convergence Analysis

| Metric | Value |
|--------|-------|
| Initial Loss (Step 1) | {all_steps[0]['loss'] if all_steps else 'N/A'} |
| Final Loss | {all_steps[-1]['loss'] if all_steps else 'N/A'} |
| Minimum Step Loss | {min_loss_str} |
| Maximum Step Loss | {max_loss_str} |
| Average Step Loss | {avg_loss_str} |
| Convergence Step (<0.1 loss) | {convergence_step if convergence_step else 'N/A'} |

### 5.3 Learning Rate Schedule

| Metric | Value |
|--------|-------|
| Max Learning Rate | {max_lr_str} |
| Min Learning Rate | {min_lr_str} |
| Warmup Steps | {config.warmup_steps} |
| Schedule Type | Linear decay with warmup |

### 5.4 Loss Curve Sample Points

| Step | Loss | Learning Rate |
|------|------|---------------|
"""
    
    for s in sampled_steps:
        md += f"| {s['step']} | {s['loss']:.4f} | {s['lr']:.2e} |\n"
    
    md += f"""
### 5.5 Training Progress Summary

- **Initial Train Loss:** {initial_loss}
- **Final Train Loss:** {final_loss}
- **Loss Reduction:** {loss_reduction_str}
- **Best Validation Loss:** {best_eval_loss_str}
- **Total Training Steps:** {actual_total_steps:,}
- **Steps per Epoch:** ~{steps_per_epoch:,}

---

## 6. Performance Metrics

| Metric | Epoch 1 | Epoch 2 | Epoch 3 |
|--------|---------|---------|---------|
"""
    
    for i, metric_name in enumerate(['eval_runtime', 'eval_samples_per_second', 'eval_steps_per_second']):
        row = f"| {metric_name.replace('_', ' ').title()} |"
        for e in epochs_data[:3]:
            val = e.get(metric_name, 'N/A')
            if isinstance(val, float):
                row += f" {val:.2f} |"
            else:
                row += f" {val} |"
        md += row + "\n"
    
    # ============ INFERENCE COST SECTION ============
    if inference_stats:
        latency = inference_stats.get("latency", {})
        gen_lat = latency.get("generation", {})
        tok_lat = latency.get("tokenization", {})
        total_lat = latency.get("total_e2e", {})
        token_lens = inference_stats.get("token_lengths", {})
        input_lens = token_lens.get("input", {})
        output_lens = token_lens.get("output", {})
        vram = inference_stats.get("vram", {})
        nvidia_smi = vram.get("nvidia_smi", {})
        throughput = inference_stats.get("batch_throughput", {})
        decoding = inference_stats.get("decoding_comparison", {})
        
        md += f"""
---

## 7. Inference Cost Analysis

### 7.1 Configuration

| Parameter | Value |
|-----------|-------|
| Device | {inference_stats.get('gpu_name', 'N/A')} |
| Model Precision | {inference_stats.get('model_dtype', 'float32')} |
| FP16 Enabled | {'Yes' if inference_stats.get('fp16_enabled', False) else 'No'} |
| Max Length | {inference_stats.get('max_length', 512)} |
| Decoding Strategy | Greedy (num_beams={inference_stats.get('num_beams_default', 1)}) |
| Samples Measured | {inference_stats.get('samples_measured', 0)} |

### 7.2 Latency Breakdown (Greedy, batch=1)

| Phase | Mean | P50 | P95 | P99 |
|-------|------|-----|-----|-----|
| Tokenization | {tok_lat.get('mean', 0):.1f} ms | {tok_lat.get('p50', 0):.1f} ms | {tok_lat.get('p95', 0):.1f} ms | {tok_lat.get('p99', 0):.1f} ms |
| Generation | {gen_lat.get('mean', 0):.1f} ms | {gen_lat.get('p50', 0):.1f} ms | {gen_lat.get('p95', 0):.1f} ms | {gen_lat.get('p99', 0):.1f} ms |
| **Total (E2E)** | **{total_lat.get('mean', 0):.1f} ms** | **{total_lat.get('p50', 0):.1f} ms** | **{total_lat.get('p95', 0):.1f} ms** | **{total_lat.get('p99', 0):.1f} ms** |

### 7.3 Token Length Statistics

| Metric | Input Tokens | Output Tokens |
|--------|-------------|---------------|
| Mean | {input_lens.get('mean', 0):.0f} | {output_lens.get('mean', 0):.0f} |
| P50 | {input_lens.get('p50', 0):.0f} | {output_lens.get('p50', 0):.0f} |
| P95 | {input_lens.get('p95', 0):.0f} | {output_lens.get('p95', 0):.0f} |
| Max | {input_lens.get('max', 0)} | {output_lens.get('max', 0)} |

### 7.4 GPU Memory Usage

| Measurement Method | Value |
|-------------------|-------|
| `torch.cuda.max_memory_allocated()` | {vram.get('pytorch_peak_mb', 0):.1f} MB ({vram.get('pytorch_peak_gb', 0):.2f} GB) |
| `nvidia-smi` (total process) | {nvidia_smi.get('used_mb', 'N/A')} MB / {nvidia_smi.get('total_mb', 'N/A')} MB |

> **Note:** Difference between PyTorch and nvidia-smi reflects CUDA context overhead (~800 MB).

### 7.5 Batch Throughput

| Batch Size | Throughput (samples/s) |
|------------|----------------------|
"""
        for batch_size, tput in throughput.items():
            md += f"| {batch_size} | {tput:.2f} |\n"
        
        md += f"""
### 7.6 Decoding Strategy Comparison

| Strategy | Latency (ms) | Overhead |
|----------|--------------|----------|
| Greedy (num_beams=1) | {decoding.get('greedy_ms', 0):.1f} | - |
| Beam Search (num_beams=4) | {decoding.get('beam4_ms', 0):.1f} | +{decoding.get('beam_overhead_percent', 0):.1f}% |

> Fixed input length: {decoding.get('fixed_input_tokens', 0)} tokens. Output identical: {'✅ Yes' if decoding.get('output_identical', False) else '❌ No'}.

"""
    else:
        md += """
---

> **Note:** Run `python benchmark_inference.py` to generate inference cost metrics.

"""
    
    md += f"""---

## 8. Output Artifacts


| File | Description |
|------|-------------|
| `{config.output_dir}/final_model/config.json` | Model configuration |
| `{config.output_dir}/final_model/model.safetensors` | Model weights |
| `{config.output_dir}/final_model/tokenizer.json` | Tokenizer |
| `{config.output_dir}/training_logs.json` | Detailed step-level training logs |
| `{config.output_dir}/train_report.md` | This report |

---

## 9. Recommendations for Paper

### Key Findings
1. The model achieved significant loss reduction from {initial_loss} to {final_loss} ({loss_reduction_str})
2. Training converged within {convergence_step if convergence_step else 'early'} steps
3. Best validation loss: {best_eval_loss_str}

### Suggested Metrics to Report
- **BLEU Score**: Run `evaluate_model.py` to calculate
- **CodeBLEU**: Available in metrics module
- **Exact Match Rate**: Compare predictions with ground truth

---

> **Note:** For custom visualization and loss curve plotting, use the `training_logs.json` file which contains step-level loss and learning rate data for all {actual_total_steps:,} training steps (logged every {logging_interval} steps).
"""
    
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(md)
    
    print(f"{'='*60}")
    print(f"Enhanced Training Report generated!")
    print(f"Location: {report_path}")
    print(f"{'='*60}")
    print(f"\nReport Summary:")
    print(f"  - Total Duration: {total_duration_str}")
    print(f"  - Training Steps: {actual_total_steps:,}")
    print(f"  - Best Eval Loss: {best_eval_loss_str}")
    print(f"  - Loss Reduction: {loss_reduction_str}")

if __name__ == "__main__":
    regenerate_report()
