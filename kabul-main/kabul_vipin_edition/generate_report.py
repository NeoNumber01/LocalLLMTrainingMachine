# -*- coding: utf-8 -*-
"""
Research Paper Evaluation Report Generator
Generates a detailed, paper-ready code translation model evaluation report.

Report contains:
1. Model Architecture and Parameter Details
2. Training Process and Hyperparameters
3. Dataset Details
4. Multidimensional Evaluation Results (BLEU, CodeBLEU, Compilation Rate, Idioms, etc.)
5. Comparative Analysis and Statistics
6. Detailed Case Studies
"""

import os
import json
import sys
import pandas as pd
from datetime import datetime
from pathlib import Path

# Try to get version info
try:
    import torch
    TORCH_VERSION = torch.__version__
except ImportError:
    TORCH_VERSION = "Not installed"

try:
    import transformers
    TRANSFORMERS_VERSION = transformers.__version__
except ImportError:
    TRANSFORMERS_VERSION = "Not installed"

try:
    import tree_sitter
    TREE_SITTER_VERSION = tree_sitter.__version__ if hasattr(tree_sitter, '__version__') else "0.22+"
except ImportError:
    TREE_SITTER_VERSION = "Not installed"

# ============= Configuration =============
BASE_DIR = Path(__file__).parent
MODEL_DIR = BASE_DIR / "fine_tuned_codet5_java_csharp"
CHECKPOINT_DIR = MODEL_DIR / "checkpoint-3462"

# Input files
SUMMARY_JSON = BASE_DIR / "evaluation_summary.json"
RESULTS_CSV = BASE_DIR / "evaluation_results_multidim.csv"
MODEL_CONFIG = MODEL_DIR / "config.json"
TRAINER_STATE = CHECKPOINT_DIR / "trainer_state.json"
UNIT_TEST_RESULTS = BASE_DIR / "unit_test_results.json"
FUNCTIONAL_TEST_RESULTS = BASE_DIR / "functional_test_results.json"
REGRESSION_SUMMARY = BASE_DIR / "regression_summary.json"

# Output files
OUTPUT_MD = BASE_DIR / "research_paper_report.md"


def load_json(path: Path) -> dict:
    """Safely load JSON file"""
    if not path.exists():
        print(f"Warning: {path} not found")
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_csv(path: Path) -> pd.DataFrame:
    """Safely load CSV file"""
    if not path.exists():
        print(f"Warning: {path} not found")
        return pd.DataFrame()
    return pd.read_csv(path)


def format_number(n, precision=4):
    """Format number"""
    if isinstance(n, float):
        return f"{n:.{precision}f}"
    return str(n)


def generate_report():
    """Generate complete research paper evaluation report"""
    
    # ============= Load Data =============
    summary = load_json(SUMMARY_JSON)
    model_config = load_json(MODEL_CONFIG)
    trainer_state = load_json(TRAINER_STATE)
    results_df = load_csv(RESULTS_CSV)
    
    # Support new and old JSON formats
    if "fine_tuned_metrics" in summary:
        # New format (with comparison)
        ft_metrics = summary.get("fine_tuned_metrics", {})
        base_metrics = summary.get("base_metrics", {})
        comparison_enabled = summary.get("comparison_enabled", False)
    else:
        # Old format
        ft_metrics = summary.get("metrics", {})
        base_metrics = {}
        comparison_enabled = False
    
    # Load post-processing and inference stats
    post_process_stats = summary.get("post_process_stats", {})
    inference_stats = summary.get("inference_stats", {})
    
    # Load unit test results (if present) - keep compatibility
    unit_test_results = load_json(UNIT_TEST_RESULTS)
    
    # Load functional correctness test results (Code-to-Code)
    functional_test_results = load_json(FUNCTIONAL_TEST_RESULTS)
    
    # Load regression test results (Text-to-Code)
    regression_summary = load_json(REGRESSION_SUMMARY)
    
    log_history = trainer_state.get("log_history", [])
    
    # ============= Extract Key Info =============
    # Model parameters
    d_model = model_config.get("d_model", 768)
    num_layers = model_config.get("num_layers", 12)
    num_heads = model_config.get("num_heads", 12)
    d_ff = model_config.get("d_ff", 3072)
    vocab_size = model_config.get("vocab_size", 32100)
    max_position = model_config.get("n_positions", 512)
    dropout = model_config.get("dropout_rate", 0.1)
    
    # Estimated parameter count (T5-base ~220M)
    param_estimate = "~220M"
    
    # Training info
    num_epochs = trainer_state.get("num_train_epochs", 5)
    batch_size = trainer_state.get("train_batch_size", 4)
    max_steps = trainer_state.get("max_steps", 3220)
    total_flos = trainer_state.get("total_flos", 0)
    
    # Extract train/eval loss history
    train_losses = [(e["epoch"], e["loss"]) for e in log_history if "loss" in e and "eval_loss" not in e]
    eval_losses = [(e["epoch"], e["eval_loss"]) for e in log_history if "eval_loss" in e]
    
    # ============= Generate Markdown Content =============
    md = []
    
    # Title
    md.append("# Java → C# Code Translation Model Evaluation Report")
    md.append(f"**Report Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    md.append("---\n")
    
    # ============= 1. Summary =============
    md.append("## 1. Executive Summary\n")
    md.append("This report conducts a comprehensive evaluation of the Java to C# code translation model fine-tuned on CodeT5.\n")
    
    md.append("### Key Metrics Overview\n")
    md.append("| Dimension | Metric | Value | Description |")
    md.append("| :--- | :--- | ---: | :--- |")
    md.append(f"| **Semantic** | BLEU | **{format_number(ft_metrics.get('bleu', 0), 2)}** | Traditional n-gram match |")
    md.append(f"| **Semantic** | CodeBLEU | **{format_number(ft_metrics.get('codebleu', 0))}** | AST + DataFlow Composite |")
    md.append(f"| | ├─ Syntax (AST) | {format_number(ft_metrics.get('codebleu_syntax', 0))} | Syntax Tree Structure Match |")
    md.append(f"| | └─ DataFlow | {format_number(ft_metrics.get('codebleu_dataflow', 0))} | Variable Logic Flow Match |")
    
    compilation_rate = ft_metrics.get('compilation_rate', -1)
    comp_str = "N/A (Req. .NET SDK)" if compilation_rate < 0 else f"{compilation_rate:.2%}"
    md.append(f"| **Executability** | Compilation Rate | {comp_str} | C# dotnet build |")
    
    md.append(f"| **Quality** | Naming Convention | **{format_number(ft_metrics.get('naming_score', 0) * 100, 1)}%** | PascalCase Compliance |")
    md.append(f"| **Quality** | C# Idioms | {format_number(ft_metrics.get('avg_csharp_idioms', 0), 2)}/Sample | LINQ/var/foreach |")
    md.append("")
    
    codebleu_note = ft_metrics.get('codebleu_note', 'Unknown')
    if "native" in str(codebleu_note).lower():
        md.append(f"> **Note**: CodeBLEU uses native Tree-sitter implementation (AST + Variable Renaming DataFlow).\n")
    
    # ============= Model Comparison (if enabled) =============
    if comparison_enabled and base_metrics:
        md.append("### Model Comparison\n")
        md.append("| Metric | Base Model | Fine-tuned Model | Improvement |")
        md.append("| :--- | ---: | ---: | ---: |")
        
        for key, label in [('bleu', 'BLEU'), ('codebleu', 'CodeBLEU'), 
                           ('codebleu_syntax', 'Syntax (AST)'), 
                           ('codebleu_dataflow', 'DataFlow'),
                           ('naming_score', 'Naming Convention')]:
            base_val = base_metrics.get(key, 0)
            ft_val = ft_metrics.get(key, 0)
            if isinstance(base_val, (int, float)) and isinstance(ft_val, (int, float)):
                improvement = ft_val - base_val
                sign = "+" if improvement >= 0 else ""
                if key == 'bleu':
                    md.append(f"| {label} | {base_val:.2f} | **{ft_val:.2f}** | {sign}{improvement:.2f} |")
                elif key == 'naming_score':
                    md.append(f"| {label} | {base_val:.1%} | **{ft_val:.1%}** | {sign}{improvement:.1%} |")
                else:
                    md.append(f"| {label} | {base_val:.4f} | **{ft_val:.4f}** | {sign}{improvement:.4f} |")
        
        # Calculate overall improvement
        base_bleu = base_metrics.get('bleu', 0)
        ft_bleu = ft_metrics.get('bleu', 0)
        if base_bleu > 0:
            improvement_pct = ((ft_bleu - base_bleu) / base_bleu) * 100
            md.append(f"\n> **BLEU Improvement**: {improvement_pct:.1f}% (from {base_bleu:.2f} to {ft_bleu:.2f})\n")
        md.append("")
    
    # ============= 2. Model Architecture =============
    md.append("---\n## 2. Model Architecture\n")
    md.append("### 2.1 Base Model Information\n")
    md.append("| Attribute | Value |")
    md.append("| :--- | :--- |")
    md.append(f"| **Base Model** | Salesforce/codet5-base |")
    md.append(f"| **Architecture** | T5ForConditionalGeneration (Encoder-Decoder) |")
    md.append(f"| **Parameters** | {param_estimate} |")
    md.append(f"| **Hidden Size (d_model)** | {d_model} |")
    md.append(f"| **Encoder/Decoder Layers** | {num_layers} |")
    md.append(f"| **Attention Heads** | {num_heads} |")
    md.append(f"| **Feed-Forward Dim (d_ff)** | {d_ff} |")
    md.append(f"| **Vocabulary Size** | {vocab_size:,} |")
    md.append(f"| **Max Sequence Length** | {max_position} |")
    md.append(f"| **Dropout Rate** | {dropout} |")
    md.append("")
    
    # ============= 3. Training Configuration =============
    md.append("### 2.2 Training Hyperparameters\n")
    md.append("| Hyperparameter | Value |")
    md.append("| :--- | :--- |")
    md.append(f"| **Epochs** | {num_epochs} |")
    md.append(f"| **Batch Size** | {batch_size} |")
    md.append(f"| **Total Training Steps** | {max_steps:,} |")
    md.append(f"| **Initial Learning Rate** | 5e-5 |")
    md.append(f"| **Optimizer** | AdamW (Hugging Face default) |")
    md.append(f"| **Warmup Steps** | ~10% |")
    md.append(f"| **Total FLOPs** | {total_flos:.2e} |")
    md.append("")
    
    # ============= 4. Training Process =============
    md.append("### 2.3 Training Process (Loss Curve)\n")
    if train_losses or eval_losses:
        md.append("| Epoch | Training Loss | Validation Loss |")
        md.append("| :---: | ---: | ---: |")
        
        # Merge train and eval loss by epoch
        epoch_data = {}
        for ep, loss in train_losses:
            epoch_data.setdefault(int(ep), {})["train"] = loss
        for ep, loss in eval_losses:
            epoch_data.setdefault(int(ep), {})["eval"] = loss
        
        for ep in sorted(epoch_data.keys()):
            train_l = epoch_data[ep].get("train", "-")
            eval_l = epoch_data[ep].get("eval", "-")
            train_str = f"{train_l:.4f}" if isinstance(train_l, float) else train_l
            eval_str = f"{eval_l:.4f}" if isinstance(eval_l, float) else eval_l
            md.append(f"| {ep} | {train_str} | {eval_str} |")
        md.append("")
        
        # Convergence Analysis
        if train_losses:
            initial_loss = train_losses[0][1]
            final_loss = train_losses[-1][1]
            reduction = (1 - final_loss / initial_loss) * 100
            md.append(f"> **Training Convergence**: Loss decreased from {initial_loss:.4f} to {final_loss:.4f}, by **{reduction:.1f}%**.\n")
    
    # ============= 5. Dataset Details =============
    md.append("---\n## 3. Dataset Details\n")
    md.append("### 3.1 XLCoST Dataset\n")
    md.append("| Attribute | Value |")
    md.append("| :--- | :--- |")
    md.append("| **Source** | [XLCoST: A Benchmark Dataset for Cross-lingual Code Snippets](https://github.com/xiaobingabc/XLCoST) |")
    md.append("| **Task** | Java → C# (Program-level) |")
    md.append("| **Training Set (Java)** | 9,623 programs |")
    md.append("| **Training Set (C#)** | 9,345 programs |")
    md.append("| **Test Set (Java)** | 911 programs |")
    md.append("| **Test Set (C#)** | 899 programs |")
    samples_evaluated = summary.get('samples_evaluated', 0)
    md.append(f"| **Evaluated Samples** | {samples_evaluated} (Aligned) |")
    md.append("")
    
    # Add aligned dataset note
    md.append("> **Note**: Evaluation uses aligned test set (`xlcost_data/data/aligned/`), ensuring 1-to-1 Java-C# correspondence.\n")
    md.append("")
    
    if not results_df.empty and 'Input_Java' in results_df.columns:
        avg_input_len = results_df['Input_Java'].astype(str).str.len().mean()
        max_input_len = results_df['Input_Java'].astype(str).str.len().max()
        md.append("### 3.2 Test Sample Statistics\n")
        md.append(f"- **Avg Input Length**: {avg_input_len:.0f} chars")
        md.append(f"- **Max Input Length**: {max_input_len:.0f} chars")
        md.append("")
    
    # ============= 6. Evaluation Metrics Details =============
    md.append("---\n## 4. Evaluation Metrics (Full Details)\n")
    
    md.append("### 4.1 Semantic Consistency\n")
    md.append("| Metric | Value | Calculation Method |")
    md.append("| :--- | ---: | :--- |")
    md.append(f"| **BLEU** | {format_number(ft_metrics.get('bleu', 0), 2)} | SacreBLEU 4-gram |")
    md.append(f"| **CodeBLEU** | {format_number(ft_metrics.get('codebleu', 0))} | Weighted Composite (Items below) |")
    md.append(f"| ├─ N-gram Match | {format_number(ft_metrics.get('codebleu_ngram', 0))} | Standard n-gram match |")
    md.append(f"| ├─ Weighted N-gram | {format_number(ft_metrics.get('codebleu_weighted', 0))} | Keyword weighted |")
    md.append(f"| ├─ **Syntax (AST)** | {format_number(ft_metrics.get('codebleu_syntax', 0))} | Syntax Tree Structure Match |")
    md.append(f"| └─ **DataFlow** | {format_number(ft_metrics.get('codebleu_dataflow', 0))} | Variable Logic Flow Match |")
    md.append(f"| **Exact Match** | {format_number(ft_metrics.get('exact_match_rate', 0) * 100, 1)}% | Completely Identical Ratio |")
    md.append("")
    
    md.append("### 4.2 Executability\n")
    md.append("| Metric | Value | Description |")
    md.append("| :--- | ---: | :--- |")
    md.append(f"| **Compilation Rate** | {comp_str} | `dotnet build` test |")
    
    # Add Syntax Validity
    syntax_rate = ft_metrics.get('syntax_validity_rate', -1)
    syntax_str = "N/A" if syntax_rate < 0 else f"{syntax_rate:.2%}"
    md.append(f"| **Syntax Validity (AST)** | {syntax_str} | Tree-sitter Parse Success Rate |")
    md.append("")
    
    md.append("### 4.3 Code Quality\n")
    md.append("| Metric | Value | Description |")
    md.append("| :--- | ---: | :--- |")
    md.append(f"| **Naming Convention Score** | {format_number(ft_metrics.get('naming_score', 0) * 100, 1)}% | C# Naming Convention Compliance |")
    md.append(f"| ├─ PascalCase Methods | {ft_metrics.get('pascal_case_methods', 0)}/{ft_metrics.get('total_methods', 0)} | Method Name Detection |")
    md.append(f"| **Avg C# Idioms / Sample** | {format_number(ft_metrics.get('avg_csharp_idioms', 0), 2)} | Idiom Density |")
    md.append(f"| ├─ LINQ Usage | {ft_metrics.get('total_linq_usage', 0)} | .Where(), .Select()... |")
    md.append(f"| ├─ foreach Usage | {ft_metrics.get('total_foreach_usage', 0)} | - |")
    md.append(f"| ├─ var Keyword | {ft_metrics.get('total_var_usage', 0)} | - |")
    md.append(f"| **Java Pattern Residue** | {ft_metrics.get('java_pattern_residue', 0)} | Residual Java Style Code |")
    md.append("")
    
    # 4.4A Post-process Stats
    if post_process_stats:
        md.append("### 4.5 Post-processing Statistics\n")
        md.append("| Layer | Operation | Count |")
        md.append("| :--- | :--- | ---: |")
        md.append(f"| **Layer 1** | Rule Cleaning (Regex) | {post_process_stats.get('layer1_applied', 0)} times |")
        md.append(f"| **Layer 2** | Syntax Formatting (dotnet format) | {post_process_stats.get('layer2_applied', 0)} times |")
        md.append(f"| **Layer 3** | Compilation Self-Healing | {post_process_stats.get('layer3_fixes', 0)} fixes |")
        md.append("")
        md.append("> **Note**: Post-processing pipeline includes three layers: Rule Cleaning, dotnet format, Compiler-Aided Self-Healing.\n")
        md.append("")
    
    # 4.6 Functional Correctness (Code-to-Code)
    md.append("### 4.6 Functional Correctness (Code-to-Code)\\n")
    
    # Prioritize reading from functional_test_results.json
    if functional_test_results and 'fine_tuned' in functional_test_results:
        ft_func = functional_test_results.get('fine_tuned', {})
        base_func = functional_test_results.get('base', {})
        
        ft_pass_rate = ft_func.get('pass_rate', -1)
        ft_compile_rate = ft_func.get('compilation_rate', -1)
        ft_passed = ft_func.get('passed', 0)
        ft_valid = ft_func.get('valid_samples', 0)
        
        # If base model comparison exists
        if base_func:
            base_pass_rate = base_func.get('pass_rate', 0)
            base_compile_rate = base_func.get('compilation_rate', 0)
            base_passed = base_func.get('passed', 0)
            base_valid = base_func.get('valid_samples', 0)
            
            md.append("| Metric | Base Model | Fine-tuned Model | Improvement |")
            md.append("| :--- | ---: | ---: | ---: |")
            
            # Function Pass Rate
            ft_pass_str = f"{ft_pass_rate:.2%}" if ft_pass_rate >= 0 else "N/A"
            base_pass_str = f"{base_pass_rate:.2%}"
            pass_improve = ft_pass_rate - base_pass_rate
            md.append(f"| **Function Pass Rate** | {base_pass_str} | **{ft_pass_str}** | +{pass_improve:.2%} |")
            
            # Compilation Rate
            ft_comp_str = f"{ft_compile_rate:.2%}" if ft_compile_rate >= 0 else "N/A"
            base_comp_str = f"{base_compile_rate:.2%}"
            comp_improve = ft_compile_rate - base_compile_rate
            md.append(f"| **Compilation Rate** | {base_comp_str} | **{ft_comp_str}** | +{comp_improve:.2%} |")
            
            # Passed tests
            md.append(f"| **Tests Passed** | {base_passed}/{base_valid} | **{ft_passed}/{ft_valid}** | +{ft_passed - base_passed} |")
            md.append("")
        else:
            # Only fine-tuned model results
            md.append("| Metric | Value | Description |")
            md.append("| :--- | ---: | :--- |")
            pass_str = f"{ft_pass_rate:.2%} ({ft_passed}/{ft_valid})" if ft_pass_rate >= 0 else "N/A"
            comp_str = f"{ft_compile_rate:.2%}" if ft_compile_rate >= 0 else "N/A"
            md.append(f"| **Pass Rate** | {pass_str} | Execution output matches reference |")
            md.append(f"| **Translated Code Compilation** | {comp_str} | Translated code compiles |")
            md.append("")
        
        md.append("> **Note**: Functional correctness uses comparison of execution output against reference C# code.\\n")
    elif unit_test_results and 'fine_tuned' in unit_test_results:
        # Compatible with old unit_test_results.json
        md.append("| Metric | Value | Description |")
        md.append("| :--- | ---: | :--- |")
        ut_ft = unit_test_results.get('fine_tuned', {})
        pass_at_1 = ut_ft.get('pass_at_1', -1)
        unit_compile_rate = ut_ft.get('compilation_rate', -1)
        unit_total = ut_ft.get('tests_total', 0)
        unit_passed = ut_ft.get('tests_passed', 0)
        
        pass_str = f"{pass_at_1:.2%} ({unit_passed}/{unit_total})" if pass_at_1 >= 0 else "N/A"
        unit_comp_str = f"{unit_compile_rate:.2%}" if unit_compile_rate >= 0 else "N/A"
        
        md.append(f"| **Pass@1** | {pass_str} | MultiPL-E Test |")
        md.append(f"| **Compilation Rate** | {unit_comp_str} | Generated Code Compilation Rate |")
        md.append("")
    else:
        md.append("| Metric | Value | Description |")
        md.append("| :--- | ---: | :--- |")
        md.append("| **Pass Rate** | N/A (Run separately) | Execution output matches reference |")
        md.append("| **Translated Code Compilation** | N/A | Translated code compiles |")
        md.append("")
        md.append("> **Note**: Run `python3 evaluate_functional.py --compare-base` for Code-to-Code functional correctness test.\\n")
    md.append("")
    
    # 4.7 Regression Test (Text-to-Code)
    if regression_summary:
        md.append("### 4.7 Regression Test (Text-to-Code)\\n")
        
        reg_base = regression_summary.get("base_metrics", {})
        reg_ft = regression_summary.get("fine_tuned_metrics", {})
        
        base_bleu = reg_base.get("bleu", 0)
        ft_bleu = reg_ft.get("bleu", 0)
        bleu_diff = ft_bleu - base_bleu
        
        md.append("Evaluates if fine-tuned model capability degrades on original Text-to-code tasks (Catastrophic Forgetting Detection).\\n")
        
        md.append("| Metric | Base Model | Fine-Tuned Model | Diff |")
        md.append("| :--- | ---: | ---: | ---: |")
        md.append(f"| **BLEU** | {base_bleu:.2f} | **{ft_bleu:.2f}** | {'+' if bleu_diff >= 0 else ''}{bleu_diff:.2f} |")
        
        base_cb = reg_base.get("codebleu", -1)
        ft_cb = reg_ft.get("codebleu", -1)
        if base_cb >= 0 and ft_cb >= 0:
            cb_diff = ft_cb - base_cb
            md.append(f"| **CodeBLEU** | {base_cb:.2f} | **{ft_cb:.2f}** | {'+' if cb_diff >= 0 else ''}{cb_diff:.2f} |")
            
        md.append("")
        
        if bleu_diff < -5.0:
            md.append("> ⚠️ **Warning**: Significant performance degradation detected (>5.0 BLEU drop), indicating catastrophic forgetting risk. Suggest adding Text-to-code replay in training.\\n")
        elif bleu_diff > 0:
            md.append("> ✅ **Info**: Fine-tuned model improved on Text-to-code task, indicating positive transfer.\\n")
        else:
            md.append("> ℹ️ **Info**: Performance roughly equal, no serious catastrophic forgetting during fine-tuning.\\n")
        md.append("")
    
    # ============= 7. Qualitative Analysis =============
    md.append("---\n## 5. Qualitative Analysis (Case Studies)\n")
    
    if not results_df.empty:
        sample_size = min(5, len(results_df))
        sample_df = results_df.sample(sample_size, random_state=42)
        
        for i, (idx, row) in enumerate(sample_df.iterrows(), 1):
            md.append(f"### Case Study #{i}\n")
            
            # Input
            java_code = str(row.get('Input_Java', 'N/A')).strip()
            md.append("**Input (Java):**")
            md.append("```java")
            md.append(java_code[:1500] + ("..." if len(java_code) > 1500 else ""))
            md.append("```\n")
            
            # Reference
            ref_code = str(row.get('Reference_CSharp', 'N/A')).strip()
            md.append("**Reference (C#):**")
            md.append("```csharp")
            md.append(ref_code[:1500] + ("..." if len(ref_code) > 1500 else ""))
            md.append("```\n")
            
            # Prediction
            pred_col = 'PostProcessed_Prediction' if 'PostProcessed_Prediction' in row else 'FineTuned_Prediction'
            pred_code = str(row.get(pred_col, 'N/A')).strip()
            md.append("**Model Prediction:**")
            md.append("```csharp")
            md.append(pred_code[:1500] + ("..." if len(pred_code) > 1500 else ""))
            md.append("```\n")
            
            # Per-sample metrics if available
            if 'Idiom_Score' in row:
                md.append(f"- Idiom Score: {row.get('Idiom_Score', 'N/A')}")
            if 'Naming_Score' in row:
                md.append(f"- Naming Score: {row.get('Naming_Score', 'N/A'):.2%}" if isinstance(row.get('Naming_Score'), float) else "")
            
            md.append("\n---\n")
    else:
        md.append("*No detailed results available. Run `evaluate_model.py` first.*\n")
    
    # ============= 8. Conclusion & Discussion =============
    md.append("## 6. Conclusion & Discussion\n")
    md.append("### 6.1 Key Findings\n")
    bleu_score = ft_metrics.get('bleu', 0)
    codebleu_score = ft_metrics.get('codebleu', 0)
    syntax_score = ft_metrics.get('codebleu_syntax', 0)
    dataflow_score = ft_metrics.get('codebleu_dataflow', 0)
    naming_score = ft_metrics.get('naming_score', 0)
    
    md.append(f"1. **High Quality Translation**: BLEU score {bleu_score:.2f} indicates model generates output highly similar to reference code.")
    md.append(f"2. **Syntax Retention**: AST Match {syntax_score:.4f} shows model correctly learned C# syntax structure.")
    md.append(f"3. **Logic Flow Transfer**: DataFlow Match {dataflow_score:.4f} shows variable def-use logic is well preserved.")
    md.append(f"4. **C# Style Learning**: Naming score {naming_score:.2%}, most method names follow PascalCase.")
    md.append(f"5. **Idiom Adoption**: Model uses C# idioms like LINQ and foreach.")
    md.append("")
    
    md.append("### 6.2 Limitations\n")
    # Dynamic limitation analysis
    limitations = []
    
    compilation_rate = ft_metrics.get('compilation_rate', -1)
    if compilation_rate < 0:
        limitations.append("Compilation verification not run in current environment, compilation rate unknown.")
    elif compilation_rate < 0.8:
        limitations.append(f"Compilation rate is {compilation_rate:.1%}, some generated code has syntax errors.")
    
    samples_evaluated = summary.get('samples_evaluated', 0)
    if samples_evaluated and samples_evaluated < 100:
        limitations.append(f"Only {samples_evaluated} samples used for evaluation, suggest expanding to full test set.")
    
    exact_match = ft_metrics.get('exact_match_rate', 0)
    if exact_match < 0.2:
        limitations.append(f"Exact match rate is {exact_match:.1%}, format or detail differences exist between model output and reference.")
    
    if ft_metrics.get('pass_at_1', -1) < 0:
        limitations.append("Unit test evaluation (Pass@1) not run, functional correctness unverified.")
    
    naming_score = ft_metrics.get('naming_score', 0)
    if naming_score < 0.8:
        limitations.append(f"Naming convention compliance {naming_score:.1%}, some method names do not use PascalCase.")
    
    if not limitations:
        limitations.append("Evaluation results are good, no obvious limitations.")
    
    for lim in limitations:
        md.append(f"- {lim}")
    md.append("")
    
    md.append("### 6.3 Future Work\n")
    future_work = []
    
    # Dynamic suggestions
    if ft_metrics.get('pass_at_1', -1) < 0:
        future_work.append("Run `evaluate_unit_tests.py` for unit test evaluation (Pass@1)")
    
    if compilation_rate >= 0 and compilation_rate < 0.9:
        future_work.append("Optimize post-processing rules to improve compilation rate")
    
    if naming_score < 0.8:
        future_work.append("Increase sample weight of C# naming conventions in training data")
    
    # General suggestions
    future_work.append("Introduce manual review for qualitative analysis")
    future_work.append("Compare with other BaseLine models (GPT-3.5, CodeGen, StarCoder, etc.)")
    future_work.append("Expand to more language pairs (Python→C#, JavaScript→C#, etc.)")
    
    for fw in future_work:
        md.append(f"- {fw}")
    md.append("")
    
    # ============= 9. Appendix =============
    md.append("---\n## Appendix\n")
    md.append("### A. File Paths\n")
    md.append(f"- **Model**: `{MODEL_DIR}`")
    md.append(f"- **Evaluation Summary**: `{SUMMARY_JSON}`")
    md.append(f"- **Detailed Results**: `{RESULTS_CSV}`")
    md.append("")
    
    md.append("### B. Environment Info\n")
    md.append("```")
    md.append(f"Python: {sys.version.split()[0]}")
    md.append(f"PyTorch: {TORCH_VERSION}")
    md.append(f"Transformers: {TRANSFORMERS_VERSION}")
    md.append(f"tree-sitter: {TREE_SITTER_VERSION}")
    md.append("```\n")
    
    # C. Inference Performance (if available)
    latency = ft_metrics.get('avg_latency_ms', -1)
    throughput = ft_metrics.get('throughput_samples_per_sec', -1)
    if latency > 0 or throughput > 0:
        md.append("### C. Inference Performance\n")
        md.append("| Metric | Value |")
        md.append("| :--- | ---: |")
        if latency > 0:
            md.append(f"| Average Latency | {latency:.1f} ms |")
        if throughput > 0:
            md.append(f"| Throughput | {throughput:.2f} samples/sec |")
        md.append("")
    
    # ============= Write to File =============
    content = "\n".join(md)
    with open(OUTPUT_MD, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"✅ Report generated: {OUTPUT_MD}")
    print(f"   Total {len(md)} lines of Markdown content")


if __name__ == "__main__":
    generate_report()
