# -*- coding: utf-8 -*-
"""
Multidimensional Code Translation Model Evaluation script

Evaluation Dimensions:
1. Executability: Compilation Rate
2. Semantic Consistency: BLEU, CodeBLEU (including AST/DataFlow), Exact Match
3. Code Quality: C# Idiom Density, Naming Convention Score
"""

import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
from datasets import load_dataset
import pandas as pd
from tqdm import tqdm
import os
import json
from datetime import datetime

# Import evaluation modules
from metrics.codebleu_eval import calculate_codebleu, calculate_bleu
from metrics.compilation_eval import calculate_compilation_rate, check_dotnet_available
from metrics.exact_match_eval import calculate_exact_match
from metrics.idiom_eval import calculate_batch_idiom_stats, calculate_idiom_score
from metrics.naming_eval import calculate_batch_naming_stats, check_naming_conventions
from metrics.syntax_validity_eval import calculate_syntax_validity_rate
from post_process import PostProcessor

# --- Configuration ---
BASE_MODEL_NAME = "Salesforce/codet5-base"
FINE_TUNED_MODEL_PATH = "./fine_tuned_codet5_java_csharp/final_model"
OUTPUT_FILE = "evaluation_results_multidim.csv"
SUMMARY_FILE = "evaluation_summary.json"
NUM_SAMPLES = None  # Adjustable, set to None for full evaluation
BATCH_SIZE = 1     # Maintain sequential processing to ensure stability

# ⭐ Compare with base model (will increase evaluation time by about 2x)
COMPARE_WITH_BASE = True

# Evaluation toggles
EVAL_CONFIG = {
    "bleu": True,
    "codebleu": True,
    "compilation": True,  # Requires .NET SDK
    "exact_match": True,
    "idiom_density": True,
    "naming_convention": True,
    "syntax_validity": True,  # AST syntax validity check
}


def load_models():
    """Load base model and fine-tuned model"""
    print("Loading models...")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Running on: {device}")

    # Load fine-tuned model
    print(f"Loading Fine-Tuned Model: {FINE_TUNED_MODEL_PATH}")
    try:
        ft_tokenizer = AutoTokenizer.from_pretrained(FINE_TUNED_MODEL_PATH, local_files_only=True)
        ft_model = AutoModelForSeq2SeqLM.from_pretrained(FINE_TUNED_MODEL_PATH, local_files_only=True).to(device)
    except Exception as e:
        print(f"Error loading fine-tuned model: {e}")
        return None, None, device

    # Load base model (for comparison)
    base_tokenizer, base_model = None, None
    if COMPARE_WITH_BASE:
        print(f"Loading Base Model: {BASE_MODEL_NAME}")
        try:
            base_tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_NAME)
            base_model = AutoModelForSeq2SeqLM.from_pretrained(BASE_MODEL_NAME).to(device)
        except Exception as e:
            print(f"Warning: Could not load base model: {e}")
            print("Continuing without base model comparison.")

    return (base_tokenizer, base_model), (ft_tokenizer, ft_model), device


def generate_translation(model, tokenizer, text, device, return_latency=False):
    """Generate code translation, optionally return latency"""
    import time
    
    input_text = f"Translate Java to C#; Java: {text} C#:"
    inputs = tokenizer(input_text, return_tensors="pt", truncation=True, max_length=512).to(device)
    
    if device == "cuda" or str(device).startswith("cuda"):
        torch.cuda.synchronize()
    start_time = time.perf_counter()
    
    with torch.no_grad():
        output = model.generate(
            input_ids=inputs["input_ids"],
            max_length=512,
            num_beams=1,
            early_stopping=False
        )
    
    if device == "cuda" or str(device).startswith("cuda"):
        torch.cuda.synchronize()
    latency_ms = (time.perf_counter() - start_time) * 1000
    
    result = tokenizer.decode(output[0], skip_special_tokens=True)
    
    if return_latency:
        return result, latency_ms
    return result


def evaluate_all_metrics(predictions, references, config=EVAL_CONFIG):
    """
    Run all enabled evaluation metrics
    
    Args:
        predictions: List of model-generated code
        references: List of reference code
        config: Evaluation configuration toggles
    
    Returns:
        Dictionary containing all evaluation results
    """
    results = {}
    
    # 1. BLEU Evaluation
    if config.get("bleu", True):
        print("\nCalculating BLEU score...")
        bleu_score = calculate_bleu(predictions, references)
        results["bleu"] = bleu_score
        print(f"  BLEU: {bleu_score:.2f}")
    
    # 2. CodeBLEU Evaluation (including AST and DataFlow)
    if config.get("codebleu", True):
        print("\nCalculating CodeBLEU score...")
        codebleu_result = calculate_codebleu(predictions, references, lang="c_sharp")
        results["codebleu"] = codebleu_result.get("codebleu", -1)
        results["codebleu_ngram"] = codebleu_result.get("ngram_match", -1)
        results["codebleu_weighted"] = codebleu_result.get("weighted_ngram", -1)
        results["codebleu_syntax"] = codebleu_result.get("syntax_match", -1)
        results["codebleu_dataflow"] = codebleu_result.get("dataflow_match", -1)
        results["codebleu_note"] = codebleu_result.get("note", "Unknown")
        
        if results["codebleu"] >= 0:
            print(f"  CodeBLEU: {results['codebleu']:.4f}")
            print(f"    - N-gram Match: {results['codebleu_ngram']:.4f}")
            print(f"    - Weighted N-gram: {results['codebleu_weighted']:.4f}")
            print(f"    - Syntax (AST) Match: {results['codebleu_syntax']:.4f}")
            print(f"    - DataFlow Match: {results['codebleu_dataflow']:.4f}")
        else:
            print(f"  CodeBLEU: Calculation failed - {codebleu_result.get('error', 'unknown error')}")
    
    # 3. Compilation Rate
    if config.get("compilation", True):
        print("\nCalculating compilation rate...")
        if check_dotnet_available():
            compile_result = calculate_compilation_rate(predictions, verbose=False)
            results["compilation_rate"] = compile_result["compilation_rate"]
            results["compiled_count"] = compile_result["compiled"]
            results["total_samples"] = compile_result["total"]
            print(f"  Compilation Rate: {results['compilation_rate']:.2%} ({compile_result['compiled']}/{compile_result['total']})")
        else:
            results["compilation_rate"] = -1
            print("  Compilation Rate: Skipped (NET SDK not installed)")
    
    # 4. Exact Match Rate
    if config.get("exact_match", True):
        print("\nCalculating exact match rate...")
        em_result = calculate_exact_match(predictions, references, mode="aggressive")
        results["exact_match_rate"] = em_result["exact_match_rate"]
        results["exact_matches"] = em_result["matches"]
        print(f"  Exact Match Rate: {results['exact_match_rate']:.2%} ({em_result['matches']}/{em_result['total']})")
    
    # 5. Idiom Density
    if config.get("idiom_density", True):
        print("\nCalculating C# idiom density...")
        idiom_result = calculate_batch_idiom_stats(predictions)
        results["avg_csharp_idioms"] = idiom_result["averages"]["avg_total_idioms"]
        results["total_linq_usage"] = idiom_result["csharp_idioms"].get("linq", 0)
        results["total_var_usage"] = idiom_result["csharp_idioms"].get("var_keyword", 0)
        results["total_foreach_usage"] = idiom_result["csharp_idioms"].get("foreach", 0)
        results["java_pattern_residue"] = idiom_result["java_patterns"].get("total_java_patterns", 0)
        print(f"  Average C# Idioms: {results['avg_csharp_idioms']:.2f}")
        print(f"  LINQ Usage: {results['total_linq_usage']}")
        print(f"  var Usage: {results['total_var_usage']}")
        print(f"  foreach Usage: {results['total_foreach_usage']}")
        print(f"  Java Pattern Residue: {results['java_pattern_residue']}")
    
    # 6. Naming Convention Score
    if config.get("naming_convention", True):
        print("\nCalculating naming convention score...")
        naming_result = calculate_batch_naming_stats(predictions)
        results["naming_score"] = naming_result["average_naming_score"]
        stats = naming_result["total_stats"]
        results["pascal_case_methods"] = stats["methods"]["pascal_case"]
        results["total_methods"] = stats["methods"]["total"]
        print(f"  Naming Score: {results['naming_score']:.2%}")
        print(f"  PascalCase Methods: {stats['methods']['pascal_case']}/{stats['methods']['total']}")

    # 7. Syntax Validity (AST Parse Rate)
    if config.get("syntax_validity", True):
        print("\nCalculating syntax validity (AST Parse Rate)...")
        syntax_result = calculate_syntax_validity_rate(predictions, verbose=False)
        results["syntax_validity_rate"] = syntax_result["syntax_validity_rate"]
        results["syntax_valid_count"] = syntax_result["valid_count"]
        results["syntax_error_breakdown"] = syntax_result.get("error_breakdown", {})
        print(f"  Syntax Validity Rate: {results['syntax_validity_rate']:.2%} ({syntax_result['valid_count']}/{syntax_result['total']})")
        if syntax_result.get("error_breakdown"):
            print(f"  Error Breakdown: {syntax_result['error_breakdown']}")
    
    return results


def main():
    """Main evaluation process"""
    print("=" * 60)
    print("Multidimensional Code Translation Model Evaluation")
    print("=" * 60)
    
    # 1. Load Datasets
    print("\n[1/4] Loading datasets...")
    try:
        # Use aligned datasets (generated by align_datasets.py)
        java_data = load_dataset("json", data_files={"test": "xlcost_data/data/aligned/java_aligned.json"}, split="test")
        csharp_data = load_dataset("json", data_files={"test": "xlcost_data/data/aligned/csharp_aligned.json"}, split="test")
    except Exception as e:
        print(f"Error loading datasets: {e}")
        return

    if len(java_data) != len(csharp_data):
        print(f"Warning: Dataset lengths do not match! Java: {len(java_data)}, C#: {len(csharp_data)}")
        min_len = min(len(java_data), len(csharp_data))
        java_data = java_data.select(range(min_len))
        csharp_data = csharp_data.select(range(min_len))

    if NUM_SAMPLES:
        print(f"Selecting first {NUM_SAMPLES} samples for evaluation")
        java_data = java_data.select(range(NUM_SAMPLES))
        csharp_data = csharp_data.select(range(NUM_SAMPLES))
    
    print(f"  Java Samples: {len(java_data)}")
    print(f"  C# Samples: {len(csharp_data)}")
    
    # 2. Load Models
    print("\n[2/4] Loading models...")
    (base_tok, base_mod), (ft_tok, ft_mod), device = load_models()
    if ft_mod is None:
        return

    # 3. Generate Translations
    print("\n[3/4] Generating translations...")
    results = []
    ft_preds = []
    base_preds = []  # Base model prediction
    references = []
    
    # Inference latency tracking
    ft_latencies = []
    base_latencies = []
    
    # Create post-processor (outside loop to accumulate stats)
    processor = PostProcessor(use_formatting=True, use_healing=True)

    for java_item, csharp_item in tqdm(zip(java_data, csharp_data), total=len(java_data)):
        # Data has been aligned by align_datasets.py, no need to check
        java_code = java_item['code']
        reference = csharp_item['code']
        
        # Fine-tuned model generates translation (with latency measurement)
        ft_pred, ft_lat = generate_translation(ft_mod, ft_tok, java_code, device, return_latency=True)
        ft_latencies.append(ft_lat)
        
        # Base model generates translation (if comparison is enabled)
        base_pred = "SKIPPED"
        base_lat = 0
        if base_mod is not None:
            base_pred, base_lat = generate_translation(base_mod, base_tok, java_code, device, return_latency=True)
            base_latencies.append(base_lat)
        
        # --- Post-Processing ---
        ft_pred_processed = processor.process(ft_pred)
        
        ft_preds.append(ft_pred_processed)
        base_preds.append(base_pred)
        references.append(reference)
        
        # Calculate single sample idiom score
        idiom_score = calculate_idiom_score(ft_pred_processed)
        naming_stats = check_naming_conventions(ft_pred_processed)

        results.append({
            "Input_Java": java_code,
            "Reference_CSharp": reference,
            "Base_Prediction": base_pred,
            "FineTuned_Prediction": ft_pred,
            "PostProcessed_Prediction": ft_pred_processed,
            "Idiom_Score": idiom_score,
            "Naming_Score": naming_stats["overall_score"],
            "FT_Latency_ms": ft_lat,
            "Base_Latency_ms": base_lat if base_lat else None,
        })


    # 4. Calculate Evaluation Metrics
    print("\n[4/4] Calculating evaluation metrics...")
    
    # Fine-tuned model metrics
    print("\n=== Fine-Tuned Model Metrics ===")
    ft_metrics = evaluate_all_metrics(ft_preds, references, EVAL_CONFIG)
    
    # Base model metrics (if comparison is enabled)
    base_metrics = {}
    if base_mod is not None:
        print("\n=== Base Model Metrics ===")
        base_metrics = evaluate_all_metrics(base_preds, references, EVAL_CONFIG)

    # 5. Save Results
    print("\nSaving results...")
    
    # Save detailed results CSV
    df = pd.DataFrame(results)
    df.to_csv(OUTPUT_FILE, index=False, encoding='utf-8-sig')
    print(f"  Detailed results saved: {OUTPUT_FILE}")
    
    # Save summary JSON (including comparison data)
    # Get post-processing stats
    post_process_stats = processor.get_stats()
    
    # Calculate inference performance metrics
    inference_stats = {}
    if ft_latencies:
        inference_stats["avg_latency_ms"] = sum(ft_latencies) / len(ft_latencies)
        inference_stats["throughput_samples_per_sec"] = 1000 / inference_stats["avg_latency_ms"] if inference_stats["avg_latency_ms"] > 0 else 0
        inference_stats["total_samples"] = len(ft_latencies)
    
    summary = {
        "timestamp": datetime.now().isoformat(),
        "fine_tuned_model": FINE_TUNED_MODEL_PATH,
        "base_model": BASE_MODEL_NAME if base_mod is not None else None,
        "samples_evaluated": len(ft_preds),
        "comparison_enabled": base_mod is not None,
        "fine_tuned_metrics": ft_metrics,
        "base_metrics": base_metrics if base_metrics else None,
        "post_process_stats": post_process_stats,
        "inference_stats": inference_stats,
    }
    with open(SUMMARY_FILE, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"  Evaluation summary saved: {SUMMARY_FILE}")

    # 6. Print Final Report
    print("\n" + "=" * 60)
    print("Evaluation Report Summary")
    print("=" * 60)
    print(f"Evaluation Samples: {len(ft_preds)}")
    print(f"Fine-tuned Model: {FINE_TUNED_MODEL_PATH}")
    if base_mod is not None:
        print(f"Base Model: {BASE_MODEL_NAME}")
    print("-" * 60)
    
    # Comparison Table
    if base_mod is not None:
        print("\n[Model Comparison]")
        print(f"{'Metric':<20} {'Base Model':>15} {'Fine-Tuned':>15} {'Improv.':>10}")
        print("-" * 62)
        
        for key in ['bleu', 'codebleu', 'codebleu_syntax', 'codebleu_dataflow', 'naming_score']:
            base_val = base_metrics.get(key, 0)
            ft_val = ft_metrics.get(key, 0)
            if isinstance(base_val, (int, float)) and isinstance(ft_val, (int, float)):
                improvement = ft_val - base_val
                sign = "+" if improvement >= 0 else ""
                if key == 'bleu':
                    print(f"{key:<20} {base_val:>15.2f} {ft_val:>15.2f} {sign}{improvement:>9.2f}")
                else:
                    print(f"{key:<20} {base_val:>15.4f} {ft_val:>15.4f} {sign}{improvement:>9.4f}")
    
    print("\n[Dimension 1: Executability]")
    comp_rate = ft_metrics.get("compilation_rate", -1)
    if comp_rate >= 0:
        print(f"  Compilation Rate: {comp_rate:.2%}")
    else:
        print("  Compilation Rate: N/A (Requires .NET SDK)")
    
    syntax_rate = ft_metrics.get("syntax_validity_rate", -1)
    if syntax_rate >= 0:
        print(f"  Syntax Validity Rate (AST): {syntax_rate:.2%}")
    
    print("\n[Dimension 2: Semantic Consistency]")
    bleu = ft_metrics.get('bleu', 0)
    print(f"  BLEU: {bleu:.2f}" if isinstance(bleu, (int, float)) else "  BLEU: N/A")
    codebleu = ft_metrics.get('codebleu', -1)
    if codebleu >= 0:
        print(f"  CodeBLEU: {codebleu:.4f}")
        print(f"    ├─ N-gram Match: {ft_metrics.get('codebleu_ngram', 0):.4f}")
        print(f"    ├─ Weighted N-gram: {ft_metrics.get('codebleu_weighted', 0):.4f}")
        print(f"    ├─ Syntax (AST): {ft_metrics.get('codebleu_syntax', 0):.4f}")
        print(f"    └─ DataFlow: {ft_metrics.get('codebleu_dataflow', 0):.4f}")
    else:
        print("  CodeBLEU: N/A")
    
    em_rate = ft_metrics.get('exact_match_rate', 0)
    print(f"  Exact Match Rate: {em_rate:.2%}" if isinstance(em_rate, (int, float)) else "  Exact Match Rate: N/A")
    
    print("\n[Dimension 3: Code Quality]")
    idioms = ft_metrics.get('avg_csharp_idioms', 0)
    naming = ft_metrics.get('naming_score', 0)
    print(f"  Average C# Idioms: {idioms:.2f}" if isinstance(idioms, (int, float)) else "  Average C# Idioms: N/A")
    print(f"  Naming Score: {naming:.2%}" if isinstance(naming, (int, float)) else "  Naming Score: N/A")
    
    # Inference Cost Metrics
    print("\n[Dimension 4: Inference Cost]")
    if ft_latencies:
        ft_avg_lat = sum(ft_latencies) / len(ft_latencies)
        ft_min_lat = min(ft_latencies)
        ft_max_lat = max(ft_latencies)
        ft_throughput = 1000 / ft_avg_lat  # samples/s
        
        print(f"  Fine-tuned Model:")
        print(f"    Avg Latency: {ft_avg_lat:.1f} ms")
        print(f"    Min Latency: {ft_min_lat:.1f} ms")
        print(f"    Max Latency: {ft_max_lat:.1f} ms")
        print(f"    Throughput: {ft_throughput:.2f} samples/s")
        
        # Save inference metrics to summary
        summary["inference_metrics"] = {
            "finetuned": {
                "mean_latency_ms": ft_avg_lat,
                "min_latency_ms": ft_min_lat,
                "max_latency_ms": ft_max_lat,
                "throughput_samples_per_s": ft_throughput,
                "total_samples": len(ft_latencies)
            }
        }
        
        if base_latencies:
            base_avg_lat = sum(base_latencies) / len(base_latencies)
            base_throughput = 1000 / base_avg_lat
            speedup = base_avg_lat / ft_avg_lat
            
            print(f"  Base Model:")
            print(f"    Avg Latency: {base_avg_lat:.1f} ms")
            print(f"    Throughput: {base_throughput:.2f} samples/s")
            print(f"  Speedup: Fine-Tuned vs Base = {speedup:.2f}x")
            
            summary["inference_metrics"]["base"] = {
                "mean_latency_ms": base_avg_lat,
                "throughput_samples_per_s": base_throughput
            }
            summary["inference_metrics"]["speedup"] = speedup
    else:
        print("  Inference latency data unavailable")
    
    print("\n" + "=" * 60)



if __name__ == "__main__":
    main()
