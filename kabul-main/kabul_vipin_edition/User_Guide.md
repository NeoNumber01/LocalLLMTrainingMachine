# User Guide: Java to C# Code Translation System

**Document Date**: 2026-01-25  
**Version**: 1.0

---

## 1. Introduction

This guide provides step-by-step instructions on how to use the CodeT5-based Java to C# code translation system. This system allows you to:
1.  Align and preprocess cross-lingual datasets.
2.  Fine-tune the CodeT5 model for Java-to-C# translation.
3.  Evaluate the model using multidimensional specific metrics (BLEU, CodeBLEU, Compilation Rate, etc.).
4.  Verify functional correctness using unit tests (MultiPL-E).

## 2. Prerequisites

### 2.1 Hardware Requirements
*   **GPU**: NVIDIA RTX 3080/4070 or better (min 8GB VRAM, recommended 16GB+).
*   **RAM**: 16GB+ (32GB+ recommended).
*   **Storage**: At least 10GB free space for datasets and model checkpoints.

### 2.2 Software Requirements
*   **Operating System**: Windows 10/11 (or Linux with appropriate adjustments).
*   **Python**: Version 3.10 or higher (3.11/3.12 recommended).
*   **CUDA**: Version 11.8 or 12.x compatible with PyTorch.
*   **.NET SDK**: Version 7.0 or 8.0 (Required for Compilation and Unit Tests).  
    [Download .NET SDK](https://dotnet.microsoft.com/download)

---

## 3. Installation & Setup

### 3.1 Clone Project
Ensure you are in the project root directory:
```bash
cd kabul_vipin_edition
```

### 3.2 Install Python Dependencies
Install the required libraries using `pip`:
```bash
python3 -m pip install torch transformers datasets sacrebleu tree-sitter tree-sitter-c-sharp pandas tqdm psutil
```

### 3.3 Verify Environment
Run the verification script to check GPU availability, tokenizer loading, and data alignment:
```bash
python3 verify_setup.py
```
*Expected Output:* `SUCCESS: All systems ready for training.`

---

## 4. Data Preparation

The project uses the **XLCoST** benchmark dataset. The raw data is stored in `xlcost_data/data/`.

### 4.1 Align Test Datasets
Before evaluation, reliable ground truth mapping is required. The alignment script synchronizes Java and C# test samples based on their description text.

```bash
python3 align_datasets.py
```
*   **Input**: `xlcost_data/data/Java-program-level/test.json` & `Csharp.../test.json`
*   **Output**: `xlcost_data/data/aligned/java_aligned.json` & `csharp_aligned.json`

---

## 5. Model Training

### 5.1 Configuration
Training parameters are defined in `train_config.py`. You can modify:
*   `num_train_epochs`: Number of epochs (Default: 3 or 5).
*   `learning_rate`: Default 3e-5.
*   `per_device_train_batch_size`: Adjust based on your VRAM (Default: 4).

### 5.2 Start Training
To start fine-tuning the model:
```bash
python3 train_model.py
```
*   **Process**: Loads base model -> Aligns training data -> Trains -> Saves checkpoints.
*   **Output Directory**: `fine_tuned_codet5_java_csharp/`
    *   `final_model/`: Verified best model weights.
    *   `train_report.md`: Automatic training summary.

---

## 6. Evaluation

### 6.1 Multidimensional Evaluation
Evaluate the model on semantic consistency, code quality, and compilability.

```bash
python3 evaluate_model.py
```
*   **Key Metrics**:
    *   **BLEU**: Text similarity.
    *   **CodeBLEU**: Semantic similarity (AST + DataFlow).
    *   **Compilation Rate**: Syntax correctness check (requires .NET SDK).
    *   **Naming Score**: Compliance with C# PascalCase conventions.
*   **Output**:
    *   `evaluation_results_multidim.csv`: Per-sample detailed metrics.
    *   `evaluation_summary.json`: Aggregate scores.

### 6.2 Unit Test Evaluation (Functional Correctness)
Verify if the generated code actually works using the MultiPL-E benchmark (HumanEval-CS).

```bash
python3 evaluate_unit_tests.py
```
*   **Flags**:
    *   `--num-samples 10`: Run a quick test on the first 10 samples.
    *   `--compare-base`: Compare performance against the base CodeT5 model.
    *   `--verify-canonical`: Verify if the dataset's reference solutions pass tests.
*   **Metric**: **Pass@1** (Percentage of generated functions passing provided unit tests).

### 6.3 Generate Comprehensive Report
Generate a publication-ready Markdown report summarizing all evaluation steps.

```bash
python3 generate_report.py
```
*   **Output**: `research_paper_report.md`
    *   Contains executive summary, model comparison, loss curves, and detailed case studies.

---

## 7. Troubleshooting

### 7.1 Compilation Rate is 0% or N/A
*   **Cause**: .NET SDK is not installed or not in PATH.
*   **Fix**: Install .NET SDK 7.0/8.0. Verification: Run `dotnet --version` in terminal.

### 7.2 Native CodeBLEU Falback
*   **Issue**: Logs say "Using fallback Regex implementation".
*   **Cause**: `tree-sitter` bindings might be missing or incompatible.
*   **Fix**: Ensure `tree-sitter` and `tree-sitter-c-sharp` are installed. The fallback is acceptable but less precise for AST matching.

### 7.3 CUDA/GPU Not Used
*   **Cause**: PyTorch installed without CUDA support.
*   **Fix**: Reinstall PyTorch with correct CUDA version.
    ```bash
    pip3 uninstall torch
    pip3 install torch --index-url https://download.pytorch.org/whl/cu118
    ```
    (Adjust `cu118` to your specific CUDA version).

### 7.4 "Dataset not found" Errors
*   **Cause**: `xlcost_data` folder structure is incorrect.
*   **Fix**: Ensure file structure matches:
    ```
    xlcost_data/
      data/
        Java-program-level/
        Csharp-program-level/
        aligned/ (created by align_datasets.py)
    ```

---

## 8. Directory Structure

```
kabul_vipin_edition/
├── align_datasets.py        # STEP 1: Align Data
├── train_model.py           # STEP 2: Train Model
├── evaluate_model.py        # STEP 3: General Evaluation
├── evaluate_unit_tests.py   # STEP 4: Functional Evaluation
├── generate_report.py       # STEP 5: Create Report
├── verify_setup.py          # Environment Check
├── post_process.py          # Code Cleanup Logic
├── train_config.py          # Hyperparameters
├── metrics/                 # Evaluation Modules
│   ├── compilation_eval.py
│   ├── codebleu_eval.py
│   ├── naming_eval.py
│   └── ...
└── xlcost_data/             # Dataset Directory
```
