# -*- coding: utf-8 -*-
"""
MultiPL-E Unit Test Evaluation Script
Evaluate Code Generation using MultiPL-E Benchmark (HumanEval-CS / MBPP-CS)

Usage:
    python3 evaluate_unit_tests.py                           # Full evaluation
    python3 evaluate_unit_tests.py --num-samples 20          # Quick test 20 samples
    python3 evaluate_unit_tests.py --dataset mbpp-cs         # Use MBPP-CS
    python3 evaluate_unit_tests.py --verify-canonical        # Verify canonical solution
    python3 evaluate_unit_tests.py --compare-base            # Compare with base model

Paper Writing:
    "We evaluate on MultiPL-E (HumanEval-CS), which provides translated prompts and unit tests."
"""

import argparse
import json
import os
import sys
from datetime import datetime

import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
from tqdm import tqdm

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from metrics.unit_test_eval import (
    load_multipl_e_dataset,
    run_unit_tests,
    run_canonical_solution_test,
    check_dotnet_available,
    prepare_test_code,
    USING_STATEMENTS,
)


# --- Configuration ---
BASE_MODEL_NAME = "Salesforce/codet5-base"
FINE_TUNED_MODEL_PATH = "./fine_tuned_codet5_java_csharp/final_model"
OUTPUT_FILE = "unit_test_results.json"


def load_model(model_path: str, device: str):
    """Load model and tokenizer"""
    print(f"Loading model: {model_path}")
    try:
        if model_path.startswith("./") or os.path.exists(model_path):
            tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
            model = AutoModelForSeq2SeqLM.from_pretrained(model_path, local_files_only=True).to(device)
        else:
            tokenizer = AutoTokenizer.from_pretrained(model_path)
            model = AutoModelForSeq2SeqLM.from_pretrained(model_path).to(device)
        return tokenizer, model
    except Exception as e:
        print(f"Error loading model: {e}")
        return None, None


def generate_completion(model, tokenizer, prompt: str, device: str) -> str:
    """
    Generate code completion
    
    Note: MultiPL-E prompt format differs from Java->C# translation task
    We need to adapt to the prompt format
    """
    # MultiPL-E C# prompts usually contain the function signature
    # We need the model to generate the function body
    
    # Strategy 1: Use prompt directly (suitable for fine-tuned code completion models)
    input_text = f"Complete the following C# code:\n{prompt}"
    
    inputs = tokenizer(
        input_text,
        return_tensors="pt",
        truncation=True,
        max_length=512
    ).to(device)
    
    with torch.no_grad():
        output = model.generate(
            input_ids=inputs["input_ids"],
            max_length=512,
            num_beams=1,
            early_stopping=False,
            pad_token_id=tokenizer.pad_token_id if tokenizer.pad_token_id else tokenizer.eos_token_id,
        )
    
    generated = tokenizer.decode(output[0], skip_special_tokens=True)
    return generated


def evaluate_model_on_multipl_e(
    model,
    tokenizer,
    dataset,
    device: str,
    num_samples: int = None,
    verbose: bool = True,
) -> dict:
    """
    Evaluate model on MultiPL-E dataset
    
    Returns:
        Dictionary containing Pass@1, compilation rate, etc.
    """
    samples = list(dataset)
    if num_samples:
        samples = samples[:num_samples]
    
    total = len(samples)
    passed = 0
    compiled = 0
    results = []
    
    print(f"\nEvaluating {total} samples...")
    
    for i, sample in enumerate(tqdm(samples, desc="Unit Test Evaluation")):
        prompt = sample.get("prompt", "")
        tests = sample.get("tests", "")
        name = sample.get("name", f"sample_{i}")
        
        # Generate code
        try:
            generated = generate_completion(model, tokenizer, prompt, device)
            
            # Combine prompt and generation
            # MultiPL-E prompt contains function signature, generation is function body
            full_code = prompt + generated
            
        except Exception as e:
            if verbose:
                print(f"  [{i+1}] ✗ Generation error: {e}")
            results.append({
                "name": name,
                "passed": False,
                "compiled": False,
                "error": f"generation: {e}"
            })
            continue
        
        # Run tests
        success, message, details = run_unit_tests(full_code, tests, prompt)
        
        did_compile = details.get("compilation_success", False)
        if did_compile:
            compiled += 1
        
        if success:
            passed += 1
            if verbose and i < 5:  # Only show first 5
                print(f"  [{i+1}] ✓ {name}")
        else:
            if verbose and i < 5:
                print(f"  [{i+1}] ✗ {name}: {message}")
        
        results.append({
            "name": name,
            "passed": success,
            "compiled": did_compile,
            "message": message,
            "generated_preview": generated[:200] if generated else "",
        })
    
    pass_rate = passed / total if total > 0 else 0
    compile_rate = compiled / total if total > 0 else 0
    
    return {
        "pass_at_1": pass_rate,
        "compilation_rate": compile_rate,
        "tests_passed": passed,
        "tests_compiled": compiled,
        "tests_total": total,
        "detailed_results": results,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate models on MultiPL-E benchmark (C# unit tests)"
    )
    parser.add_argument(
        "--dataset", 
        type=str, 
        default="humaneval-cs",
        choices=["humaneval-cs", "mbpp-cs"],
        help="MultiPL-E subset to use"
    )
    parser.add_argument(
        "--num-samples", 
        type=int, 
        default=None,
        help="Number of samples to evaluate (default: all)"
    )
    parser.add_argument(
        "--compare-base",
        action="store_true",
        help="Compare with base model"
    )
    parser.add_argument(
        "--verify-canonical",
        action="store_true",
        help="Verify canonical solutions pass tests"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=OUTPUT_FILE,
        help="Output JSON file"
    )
    parser.add_argument(
        "--fine-tuned-path",
        type=str,
        default=FINE_TUNED_MODEL_PATH,
        help="Path to fine-tuned model"
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("MultiPL-E Unit Test Evaluation")
    print("=" * 60)
    
    # Check Environment
    print("\n[1] Environment Check")
    
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"  Device: {device}")
    
    if not check_dotnet_available():
        print("  ✗ .NET SDK unavailable, cannot run unit tests")
        print("  Please install .NET 8.0 SDK: https://dotnet.microsoft.com/download")
        return
    print("  ✓ .NET SDK available")
    
    # Load Dataset
    print(f"\n[2] Loading Dataset: {args.dataset}")
    dataset = load_multipl_e_dataset(args.dataset)
    if dataset is None:
        print("  ✗ Dataset load failed")
        print("  Please run: pip install datasets")
        return
    print(f"  ✓ Loaded {len(dataset)} samples")
    
    # Verify Canonical Solution
    if args.verify_canonical:
        print("\n[3] Verifying Canonical Solution")
        verify_samples = min(10, args.num_samples or 10)
        canonical_result = run_canonical_solution_test(dataset, verify_samples, verbose=True)
        print(f"\n  Canonical Pass Rate: {canonical_result['canonical_pass_rate']:.2%}")
        print(f"  ({canonical_result['passed']}/{canonical_result['total']})")
        
        if canonical_result['canonical_pass_rate'] < 0.5:
            print("\n  ⚠️ Warning: Canonical solution pass rate is low, there might be test environment issues")
        print()
    
    # Load Model
    print("\n[4] Loading Model")
    ft_tokenizer, ft_model = load_model(args.fine_tuned_path, device)
    if ft_model is None:
        print("  ✗ Fine-tuned model load failed")
        return
    print(f"  ✓ Fine-tuned model loaded")
    
    base_tokenizer, base_model = None, None
    if args.compare_base:
        base_tokenizer, base_model = load_model(BASE_MODEL_NAME, device)
        if base_model:
            print(f"  ✓ Base model loaded")
    
    # Evaluation
    results = {
        "timestamp": datetime.now().isoformat(),
        "dataset": args.dataset,
        "num_samples": args.num_samples or len(dataset),
        "device": device,
    }
    
    print("\n[5] Evaluating Fine-tuned Model")
    ft_results = evaluate_model_on_multipl_e(
        ft_model, ft_tokenizer, dataset, device,
        num_samples=args.num_samples,
        verbose=True
    )
    results["fine_tuned"] = {
        "model": args.fine_tuned_path,
        "pass_at_1": ft_results["pass_at_1"],
        "compilation_rate": ft_results["compilation_rate"],
        "tests_passed": ft_results["tests_passed"],
        "tests_compiled": ft_results["tests_compiled"],
        "tests_total": ft_results["tests_total"],
    }
    
    if args.compare_base and base_model:
        print("\n[6] Evaluating Base Model")
        base_results = evaluate_model_on_multipl_e(
            base_model, base_tokenizer, dataset, device,
            num_samples=args.num_samples,
            verbose=True
        )
        results["base"] = {
            "model": BASE_MODEL_NAME,
            "pass_at_1": base_results["pass_at_1"],
            "compilation_rate": base_results["compilation_rate"],
            "tests_passed": base_results["tests_passed"],
            "tests_compiled": base_results["tests_compiled"],
            "tests_total": base_results["tests_total"],
        }
    
    # Save Results
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n  Results saved to: {args.output}")
    
    # Print Report
    print("\n" + "=" * 60)
    print("Evaluation Report")
    print("=" * 60)
    print(f"Dataset: {args.dataset}")
    print(f"Samples: {results['num_samples']}")
    print()
    
    print("[Fine-tuned Model]")
    print(f"  Pass@1: {ft_results['pass_at_1']:.2%}")
    print(f"  Compilation Rate: {ft_results['compilation_rate']:.2%}")
    print(f"  Tests Passed: {ft_results['tests_passed']}/{ft_results['tests_total']}")
    
    if args.compare_base and base_model:
        print("\n[Base Model]")
        print(f"  Pass@1: {base_results['pass_at_1']:.2%}")
        print(f"  Compilation Rate: {base_results['compilation_rate']:.2%}")
        print(f"  Tests Passed: {base_results['tests_passed']}/{base_results['tests_total']}")
        
        print("\n[Comparison]")
        improvement = ft_results["pass_at_1"] - base_results["pass_at_1"]
        print(f"  Pass@1 Improvement: {'+' if improvement >= 0 else ''}{improvement:.2%}")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
