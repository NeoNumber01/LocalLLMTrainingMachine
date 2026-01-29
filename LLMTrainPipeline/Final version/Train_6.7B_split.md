# Train 6.7B split

> Training Report | Generated: 2026-01-29 00:48:10

## Overview

| Property | Value |
|----------|-------|
| Run ID | `run_42548` |
| Duration | 1h 18m |
| Seed | 42 |
| Git Commit | `ba2899a` |

## Key Metrics

| Metric | Value |
|--------|-------|
| **Pass@1** | N/A |
| Compile Rate | N/A |
| Final Loss | 0.2956 |
| Planned Steps | 200 |
| **Effective Update Steps** | **40** |
| Trainable Params | 39.98M |
| Trainable % | 1.1285% |

## Model

| Property | Value |
|----------|-------|
| Model Name | deepseek-coder-6.7b-instruct |
| Model Path | storage\models\deepseek-coder-6.7b-instruct |
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
| Mean | 146.2 | N/A |
| Median (P50) | 125 | N/A |
| P95 | 289 | N/A |
| Max | 598 | N/A |

### Truncation & Data Quality

| Metric | Training Set | Eval Set |
|--------|-------------|----------|
| Max Seq Length | 512 | N/A |
| Truncation Rate | 0.06% | N/A |
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
| Trainable Parameters | 39.98M |
| Total Parameters | 3.54B |
| Trainable Percentage | 1.1285% |

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
| 1 | 0.4727 | 0.3365 | 1.1809 | N/A |
| 2 | 0.3037 | 0.2895 | 0.3201 | N/A |

### Training Convergence Analysis

| Metric | Value |
|--------|-------|
| Initial Loss (first effective update, Step 10) | 1.1809 |
| Final Loss (Step 201) | 0.2956 |
| **Loss Reduction** | **75.0%** |
| Minimum Step Loss | 0.2895 |
| Maximum Step Loss | 1.1809 |
| Average Step Loss | 0.3882 |
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
| 10 | 1.1809 | 9.99e-05 |
| 11 | 1.1809 | 9.99e-05 |
| 21 | 0.6147 | 9.89e-05 |
| 30 | 0.4103 | 9.66e-05 |
| 40 | 0.4226 | 9.30e-05 |
| 41 | 0.4226 | 9.30e-05 |
| 50 | 0.3830 | 8.84e-05 |
| 60 | 0.3453 | 8.27e-05 |
| 61 | 0.3453 | 8.27e-05 |
| 71 | 0.3447 | 7.62e-05 |
| 80 | 0.3365 | 6.89e-05 |
| 81 | 0.3365 | 6.89e-05 |
| 91 | 0.3402 | 6.12e-05 |
| 100 | 0.3488 | 5.32e-05 |
| 110 | 0.3192 | 4.51e-05 |
| 111 | 0.3192 | 4.51e-05 |
| 120 | 0.3168 | 3.72e-05 |
| 130 | 0.2931 | 2.96e-05 |
| 131 | 0.2931 | 2.96e-05 |
| 140 | 0.3201 | 2.25e-05 |
| 150 | 0.2982 | 1.61e-05 |
| 151 | 0.2982 | 1.61e-05 |
| 161 | 0.3032 | 1.06e-05 |
| 170 | 0.2895 | 6.17e-06 |
| 171 | 0.2895 | 6.17e-06 |
| 181 | 0.2938 | 2.86e-06 |
| 190 | 0.3073 | 7.91e-07 |
| 200 | 0.2956 | 6.56e-09 |
| 201 | 0.2956 | 6.56e-09 |

### Training Progress Summary

- **Initial Train Loss (Step 10):** 1.1809
- **Final Train Loss (Step 201):** 0.2956
- **Loss Reduction:** 75.0%
- **Best Step Loss:** 0.2895
- **Total Training Steps:** 40 (Steps 10–201)


## Raw Configuration

<details>
<summary>Click to expand full configuration JSON</summary>

```json
{
  "run_name": "Train 6.7B split",
  "run_id": "run_42548",
  "seed": 42,
  "start_time": "2026-01-22T01:11:49.812Z",
  "end_time": "2026-01-22T02:30:48.054Z",
  "duration": "1h 18m",
  "git_commit": "ba2899a3",
  "model": {
    "name": "deepseek-coder-6.7b-instruct",
    "path": "storage\\models\\deepseek-coder-6.7b-instruct",
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

*Report generated by LLMTrainPipeline | 2026-01-29T00:48:10.598625*