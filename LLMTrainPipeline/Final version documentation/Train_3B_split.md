# Train 3B split

> Training Report | Generated: 2026-01-29 00:52:48

## Overview

| Property | Value |
|----------|-------|
| Run ID | `run_fb297` |
| Duration | 1h 39m |
| Seed | 42 |
| Git Commit | `ba2899a` |

## Key Metrics

| Metric | Value |
|--------|-------|
| **Pass@1** | N/A |
| Compile Rate | N/A |
| Final Loss | 0.3333 |
| Planned Steps | 200 |
| **Effective Update Steps** | **40** |
| Trainable Params | 29.93M |
| Trainable % | 1.7317% |

## Model

| Property | Value |
|----------|-------|
| Model Name | qwen2.5-coder-3B-Instruct |
| Model Path | storage\models\qwen2.5-coder-3B-Instruct |
| Parameters | Unknown |
| Quantization | 4bit |

## Dataset

| Property | Value |
|----------|-------|
| Dataset Name | train_split |
| Dataset Path | C:\Users\Shu Leo\Desktop\practical course\LLMTrainPipeline\backend\storage\final refined version\train_split.jsonl |
| Total Samples | 1600 |
| Train Samples | 1600 |
| Total Tokens | 1.64M |

## Dataset Quality Analysis

> Quality Score: **100.0/100**

### Token Length Distribution

| Statistic | Training Set | Eval Set |
|-----------|-------------|----------|
| Mean | 117.8 | N/A |
| Median (P50) | 101 | N/A |
| P95 | 237 | N/A |
| Max | 511 | N/A |

### Truncation & Data Quality

| Metric | Training Set | Eval Set |
|--------|-------------|----------|
| Max Seq Length | 512 | N/A |
| Truncation Rate | 0.00% | N/A |
| Empty Samples | 0 | N/A |
| Short Samples (<10 tok) | 0 (0.00%) | N/A |

## Training Configuration

| Parameter | Value |
|-----------|-------|
| Batch Size | 1 |
| Gradient Accumulation | 16 |
| **Effective Batch Size** | 16 |
| Config Learning Rate | 1e-4 |
| Actual Initial LR | 9.99e-05 |
| LR Scheduler | cosine |
| Warmup Ratio | 0.03 |
| Epochs | 2 |
| Max Sequence Length | 512 |
| Optimizer | paged_adamw_8bit |
| Weight Decay | 0.01 |
| Precision | none |

## LoRA Configuration

| Parameter | Value |
|-----------|-------|
| Enabled | Yes |
| Rank (r) | 16 |
| Alpha | 32 |
| Dropout | 0.05 |
| Target Modules | q_proj, k_proj, v_proj, o_proj, gate_proj, up_proj, down_proj |
| Quantization | 4bit |
| Trainable Parameters | 29.93M |
| Total Parameters | 1.73B |
| Trainable Percentage | 1.7317% |

## Evaluation Results

### Pass@k Metrics

| Metric | Value |
|--------|-------|
| **Pass@1** | N/A |
| Pass@5 | N/A |
| Pass@10 | N/A |
| Compile Rate | N/A |

### Error Distribution

| Error Type | Rate |
|------------|------|
| Syntax Error | N/A |
| Runtime Error | N/A |
| Timeout | N/A |
| Assertion Error | N/A |
| Import Error | N/A |
| Memory Error | N/A |

### Execution Time Statistics

| Metric | Value |
|--------|-------|
| Mean Runtime | N/A |
| P50 Runtime | N/A |
| P95 Runtime | N/A |
| Max Runtime | N/A |

## Environment

| Component | Version |
|-----------|---------|
| OS | Windows 11 |
| Python | 3.12.10 |
| PyTorch | 2.6.0.dev20241112+cu121 |
| Transformers | 4.57.6 |
| TRL | 0.27.0 |
| PEFT | 0.18.1 |
| CUDA | 12.1 |
| cuDNN | 90100 |

## Hardware

| Component | Details |
|-----------|---------|
| GPU | NVIDIA GeForce RTX 4070 Laptop GPU |
| GPU Memory | 8 |
| CPU | AMD64 Family 25 Model 68 Stepping 1, AuthenticAMD |
| RAM | 15.24 |

## Training Results

### Per-Epoch Metrics

| Epoch | Avg Train Loss | Min Loss | Max Loss | Eval Loss |
|-------|---------------|----------|----------|-----------|
| 1 | 0.6045 | 0.3815 | 1.9334 | N/A |
| 2 | 0.3423 | 0.3271 | 0.3592 | N/A |

### Training Convergence Analysis

| Metric | Value |
|--------|-------|
| Initial Loss (first effective update, Step 10) | 1.9334 |
| Final Loss (Step 201) | 0.3333 |
| **Loss Reduction** | **82.8%** |
| Minimum Step Loss | 0.3271 |
| Maximum Step Loss | 1.9334 |
| Average Step Loss | 0.4734 |
| Total Training Steps | 40 |

> **Note:** Initial and final loss are from effective training steps (with non-zero learning rate). Pre-update warmup steps are excluded.

### Learning Rate Schedule

| Metric | Value |
|--------|-------|
| Max Learning Rate | 9.99e-05 |
| Min Learning Rate | 6.56e-09 |
| Schedule Type | cosine |

### Loss Curve Sample Points

| Step | Loss | Learning Rate |
|------|------|--------------|
| 10 | 1.9334 | 9.99e-05 |
| 11 | 1.9334 | 9.99e-05 |
| 21 | 0.7748 | 9.89e-05 |
| 30 | 0.4583 | 9.66e-05 |
| 40 | 0.4790 | 9.30e-05 |
| 41 | 0.4790 | 9.30e-05 |
| 50 | 0.4310 | 8.84e-05 |
| 60 | 0.3876 | 8.27e-05 |
| 61 | 0.3876 | 8.27e-05 |
| 71 | 0.3949 | 7.62e-05 |
| 80 | 0.3815 | 6.89e-05 |
| 81 | 0.3815 | 6.89e-05 |
| 91 | 0.4032 | 6.12e-05 |
| 100 | 0.4015 | 5.32e-05 |
| 110 | 0.3547 | 4.51e-05 |
| 111 | 0.3547 | 4.51e-05 |
| 120 | 0.3537 | 3.72e-05 |
| 130 | 0.3295 | 2.96e-05 |
| 131 | 0.3295 | 2.96e-05 |
| 140 | 0.3592 | 2.25e-05 |
| 150 | 0.3353 | 1.61e-05 |
| 151 | 0.3353 | 1.61e-05 |
| 161 | 0.3450 | 1.06e-05 |
| 170 | 0.3271 | 6.17e-06 |
| 171 | 0.3271 | 6.17e-06 |
| 181 | 0.3391 | 2.86e-06 |
| 190 | 0.3459 | 7.91e-07 |
| 200 | 0.3333 | 6.56e-09 |
| 201 | 0.3333 | 6.56e-09 |

### Training Progress Summary

- **Initial Train Loss (Step 10):** 1.9334
- **Final Train Loss (Step 201):** 0.3333
- **Loss Reduction:** 82.8%
- **Best Step Loss:** 0.3271
- **Total Training Steps:** 40 (Steps 10–201)


## Raw Configuration

<details>
<summary>Click to expand full configuration JSON</summary>

```json
{
  "run_name": "Train 3B split",
  "run_id": "run_fb297",
  "seed": 42,
  "start_time": "2026-01-22T22:38:00.321Z",
  "end_time": "2026-01-23T00:17:25.207Z",
  "duration": "1h 39m",
  "git_commit": "ba2899a3",
  "model": {
    "name": "qwen2.5-coder-3B-Instruct",
    "path": "storage\\models\\qwen2.5-coder-3B-Instruct",
    "params": "Unknown"
  },
  "dataset": {
    "name": "train_split",
    "path": "C:\\Users\\Shu Leo\\Desktop\\practical course\\LLMTrainPipeline\\backend\\storage\\final refined version\\train_split.jsonl",
    "samples": 1600,
    "train_samples": 1600,
    "val_samples": null,
    "total_tokens": 1638400
  },
  "training": {
    "lr": "1e-4",
    "epochs": 2,
    "batchSize": 1,
    "gradAccum": 16,
    "gradientAccumulation": 16,
    "maxSeqLen": 512,
    "maxLength": 512,
    "warmupRatio": 0.03,
    "weightDecay": 0.01,
    "optimizer": "paged_adamw_8bit",
    "scheduler": "cosine",
    "precision": "none",
    "total_steps": 200,
    "raw_logged_steps": 40,
    "effective_steps": 40
  },
  "lora": {
    "enabled": true,
    "rank": 16,
    "alpha": 32,
    "targetModules": [
      "q_proj",
      "k_proj",
      "v_proj",
      "o_proj",
      "gate_proj",
      "up_proj",
      "down_proj"
    ],
    "quantization": "4bit",
    "dropout": 0.05
  },
  "lr": "1e-4",
  "epochs": 2,
  "batchSize": 1,
  "maxSeqLen": 512,
  "gradAccum": 16,
  "warmupRatio": 0.03,
  "warmupType": "ratio",
  "warmupSteps": 0,
  "weightDecay": 0.01,
  "optimizer": "paged_adamw_8bit",
  "scheduler": "cosine",
  "precision": "none",
  "gradientClipping": 1,
  "loggingSteps": 10,
  "saveSteps": 100,
  "saveTotalLimit": 3,
  "evalStrategy": "epoch",
  "evalSteps": 200,
  "earlyStoppingEnabled": false,
  "earlyStoppingPatience": 3,
  "earlyStoppingThreshold": 0,
  "loadBestModelAtEnd": true,
  "metricForBestModel": "loss",
  "useLora": true,
  "loraRank": 16,
  "loraAlpha": 32,
  "loraDropout": 0.05,
  "loraBias": "none",
  "loraTargetModules": [
    "q_proj",
    "k_proj",
    "v_proj",
    "o_proj",
    "gate_proj",
    "up_proj",
    "down_proj"
  ],
  "quantization": "4bit"
}
```

</details>

---

*Report generated by LLMTrainPipeline | 2026-01-29T00:52:48.921645*