# CodeT5 Java to C# Translation - Training Report

**Generated:** 2026-01-15 18:24:11  
**Total Training Duration:** 4:52:01  
**Best Validation Loss:** 0.056959

---

## 1. Executive Summary

| Metric | Value |
|--------|-------|
| Total Training Time | 4:52:01 |
| Training Samples | 9,228 |
| Validation Samples | 486 |
| Total Training Steps | 3,460 |
| Initial Train Loss | 0.6185 |
| Final Train Loss | 0.0529 |
| Loss Reduction | 91.5% |
| Best Eval Loss | 0.056959 |

---

## 2. System Environment

| Component | Details |
|-----------|---------|
| **Hardware** | |
| GPU | NVIDIA GeForce RTX 4070 Laptop GPU |
| GPU Count | 1 |
| VRAM | 8.0 GB |
| CUDA Version | 12.4 |
| CPU | AMD64 Family 25 Model 68 Stepping 1, AuthenticAMD |
| RAM | 15.24 GB |
| **Software** | |
| OS | Windows-11-10.0.26100-SP0 |
| Python | 3.12.10 |
| PyTorch | 2.6.0+cu124 |
| Transformers | 4.57.5 |

---

## 3. Dataset Statistics

### 3.1 Raw Data & Deduplication

| Metric | Training Set | Validation Set |
|--------|-------------|----------------|
| Raw Java Samples | 9,623 | 494 |
| Raw C# Samples | 9,345 | 491 |
| Aligned Pairs (before dedup) | 9,301 | 491 |
| **Final Pairs (after dedup)** | **9,228** | **486** |
| Duplicates Removed | 73 | 5 |
| Deduplication Rate | 0.78% | 1.02% |

### 3.2 Token Length Distribution

| Language | Mean | Median (P50) | P95 | Max |
|----------|------|--------------|-----|-----|
| Java (Train) | 253.8 | 223 | 524 | 1868 |
| C# (Train) | 247.1 | 216 | 517 | 1865 |
| Java (Valid) | 246.0 | 220 | 494 | 1289 |
| C# (Valid) | 240.1 | 213 | 473 | 1291 |

### 3.3 Truncation & Data Quality

| Metric | Training Set | Validation Set |
|--------|-------------|----------------|
| Max Sequence Length | 512 | 512 |
| Java Truncation Rate | 5.47% | 4.12% |
| C# Truncation Rate | 5.20% | 3.70% |
| Empty Samples | 0 | 0 |
| Very Short Samples (<10 tokens) | 0 (0.00%) | 0 (0.00%) |

### 3.4 Train-Valid Leakage Check (Enhanced)

| Detection Method | Java | C# |
|-----------------|------|-----|
| Exact Match | 1 (0.21%) | 1 (0.21%) |
| Normalized Match (no whitespace/comments) | 1 (0.21%) | 1 (0.21%) |
| High Similarity (Jaccard >0.8) | 0 (0.00%) | 0 (0.00%) |

**Leakage Assessment:** ✅ Clean - No significant leakage detected

**Data Source:**
- Java Training: `xlcost_data/data/Java-program-level/train.json`
- C# Training: `xlcost_data/data/Csharp-program-level/train.json`
- Java Validation: `xlcost_data/data/Java-program-level/valid.json`
- C# Validation: `xlcost_data/data/Csharp-program-level/valid.json`


---

## 4. Model Configuration

### 4.1 Base Model Architecture
| Parameter | Value |
|-----------|-------|
| Model Name | `Salesforce/codet5-base` |
| Architecture | Encoder-Decoder (T5-based) |
| Total Parameters | 222,882,048 |
| Trainable Parameters | 222,882,048 |
| Frozen Parameters | 0 |
| Model Size | 850.23 MB |

### 4.2 Training Hyperparameters
| Parameter | Value | Description |
|-----------|-------|-------------|
| Learning Rate | 3e-05 | Peak learning rate |
| Batch Size (per device) | 4 | Samples per GPU |
| Gradient Accumulation | 2 | Steps to accumulate |
| **Effective Batch Size** | **8** | Total samples per update |
| Epochs | 3 | Training iterations |
| Weight Decay | 0.01 | L2 regularization |
| Warmup Steps | 500 | LR warmup period |
| Max Sequence Length | 512 | Token limit |
| Mixed Precision (FP16) | Enabled | Memory optimization |
| Logging Steps | 10 | Log frequency |
| Save Strategy | epoch | Checkpoint strategy |

---

## 5. Training Results

### 5.1 Per-Epoch Metrics

| Epoch | Train Loss | Eval Loss | Duration | Eval Throughput |
|-------|------------|-----------|----------|-----------------|
| 1 | 0.6185 | 0.0669 | 98.5 min | 21.6 samples/s |
| 2 | 0.0642 | 0.0584 | 97.0 min | 21.6 samples/s |
| 3 | 0.0529 | 0.0570 | 96.5 min | 21.7 samples/s |

### 5.2 Training Convergence Analysis

| Metric | Value |
|--------|-------|
| Initial Loss (Step 1) | 11.2226 |
| Final Loss | 0.0588 |
| Minimum Step Loss | 0.0314 |
| Maximum Step Loss | 11.2226 |
| Average Step Loss | 0.2447 |
| Convergence Step (<0.1 loss) | 440 |

### 5.3 Learning Rate Schedule

| Metric | Value |
|--------|-------|
| Max Learning Rate | 2.99e-05 |
| Min Learning Rate | 6.08e-08 |
| Warmup Steps | 500 |
| Schedule Type | Linear decay with warmup |

### 5.4 Loss Curve Sample Points

| Step | Loss | Learning Rate |
|------|------|---------------|
| 10 | 11.2226 | 3.60e-07 |
| 870 | 0.1345 | 2.63e-05 |
| 1740 | 0.0830 | 1.75e-05 |
| 2600 | 0.0406 | 8.77e-06 |
| 3460 | 0.0588 | 6.08e-08 |

### 5.5 Training Progress Summary

- **Initial Train Loss:** 0.6185
- **Final Train Loss:** 0.0529
- **Loss Reduction:** 91.5%
- **Best Validation Loss:** 0.056959
- **Total Training Steps:** 3,460
- **Steps per Epoch:** ~1,153

---

## 6. Performance Metrics

| Metric | Epoch 1 | Epoch 2 | Epoch 3 |
|--------|---------|---------|---------|
| Eval Runtime | 22.50 | 22.46 | 22.44 |
| Eval Samples Per Second | 21.59 | 21.64 | 21.66 |
| Eval Steps Per Second | 5.42 | 5.43 | 5.44 |

---

## 7. Inference Cost Analysis

### 7.1 Configuration

| Parameter | Value |
|-----------|-------|
| Device | NVIDIA GeForce RTX 4070 Laptop GPU |
| Model Precision | torch.float32 |
| FP16 Enabled | No |
| Max Length | 512 |
| Decoding Strategy | Greedy (num_beams=1) |
| Samples Measured | 50 |

### 7.2 Latency Breakdown (Greedy, batch=1)

| Phase | Mean | P50 | P95 | P99 |
|-------|------|-----|-----|-----|
| Tokenization | 1.0 ms | 0.8 ms | 1.6 ms | 2.0 ms |
| Generation | 5364.0 ms | 4332.6 ms | 12906.6 ms | 14704.6 ms |
| **Total (E2E)** | **5364.9 ms** | **4333.5 ms** | **12908.4 ms** | **14706.3 ms** |

### 7.3 Token Length Statistics

| Metric | Input Tokens | Output Tokens |
|--------|-------------|---------------|
| Mean | 233 | 220 |
| P50 | 208 | 200 |
| P95 | 466 | 449 |
| Max | 512 | 493 |

### 7.4 GPU Memory Usage

| Measurement Method | Value |
|-------------------|-------|
| `torch.cuda.max_memory_allocated()` | 956.4 MB (0.93 GB) |
| `nvidia-smi` (total process) | 1709 MB / 8188 MB |

> **Note:** Difference between PyTorch and nvidia-smi reflects CUDA context overhead (~800 MB).

### 7.5 Batch Throughput

| Batch Size | Throughput (samples/s) |
|------------|----------------------|
| 1 | 0.16 |
| 4 | 0.46 |
| 8 | 0.70 |

### 7.6 Decoding Strategy Comparison

| Strategy | Latency (ms) | Overhead |
|----------|--------------|----------|
| Greedy (num_beams=1) | 6523.7 | - |
| Beam Search (num_beams=4) | 8111.4 | +24.3% |

> Fixed input length: 358 tokens. Output identical: ✅ Yes.

---

## 8. Output Artifacts


| File | Description |
|------|-------------|
| `./fine_tuned_codet5_java_csharp/final_model/config.json` | Model configuration |
| `./fine_tuned_codet5_java_csharp/final_model/model.safetensors` | Model weights |
| `./fine_tuned_codet5_java_csharp/final_model/tokenizer.json` | Tokenizer |
| `./fine_tuned_codet5_java_csharp/training_logs.json` | Detailed step-level training logs |
| `./fine_tuned_codet5_java_csharp/train_report.md` | This report |

---

## 9. Recommendations for Paper

### Key Findings
1. The model achieved significant loss reduction from 0.6185 to 0.0529 (91.5%)
2. Training converged within 440 steps
3. Best validation loss: 0.056959

### Suggested Metrics to Report
- **BLEU Score**: Run `evaluate_model.py` to calculate
- **CodeBLEU**: Available in metrics module
- **Exact Match Rate**: Compare predictions with ground truth

---

> **Note:** For custom visualization and loss curve plotting, use the `training_logs.json` file which contains step-level loss and learning rate data for all 3,460 training steps (logged every 10 steps).
