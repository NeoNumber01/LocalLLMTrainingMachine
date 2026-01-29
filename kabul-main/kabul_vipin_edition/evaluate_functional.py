# -*- coding: utf-8 -*-
"""
Code-to-Code Functional Correctness Evaluation
Functional Correctness Evaluation for Java→C# Translation

Process:
1. Read Java code
2. Translate to C# code using the model
3. Compile and run C# code
4. Compare output with reference C# code execution result

Usage:
    python3 evaluate_functional.py                    # Full evaluation
    python3 evaluate_functional.py --num-samples 30   # Fast test
    python3 evaluate_functional.py --compare-base     # Compare with base model
"""

import argparse
import json
import os
import sys
import subprocess
import tempfile
import shutil
from datetime import datetime
from pathlib import Path

import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
from datasets import load_dataset
from tqdm import tqdm

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from post_process import PostProcessor

# --- Configuration ---
BASE_MODEL_NAME = "Salesforce/codet5-base"
FINE_TUNED_MODEL_PATH = "./fine_tuned_codet5_java_csharp/final_model"
OUTPUT_FILE = "functional_test_results.json"


def check_dotnet_available() -> bool:
    """Check if .NET SDK is available"""
    try:
        result = subprocess.run(
            ["dotnet", "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.returncode == 0
    except Exception:
        return False


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


def generate_translation(model, tokenizer, java_code: str, device: str) -> str:
    """Generate Java→C# translation"""
    input_text = f"Translate Java to C#; Java: {java_code} C#:"
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
            early_stopping=False
        )
    
    return tokenizer.decode(output[0], skip_special_tokens=True)


def run_csharp_code(code: str, timeout: int = 10) -> tuple:
    """
    Compile and run C# code
    
    Returns:
        (success, output, error_message)
    """
    temp_dir = tempfile.mkdtemp(prefix="csharp_exec_")
    
    try:
        # Create .csproj file
        csproj_content = '''<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net8.0</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>
    <Nullable>disable</Nullable>
  </PropertyGroup>
</Project>'''
        
        csproj_path = os.path.join(temp_dir, "Test.csproj")
        with open(csproj_path, 'w') as f:
            f.write(csproj_content)
        
        # Write code file
        code_path = os.path.join(temp_dir, "Program.cs")
        with open(code_path, 'w', encoding='utf-8') as f:
            f.write(code)
        
        # Run code
        result = subprocess.run(
            ["dotnet", "run", "--project", temp_dir],
            capture_output=True,
            encoding='utf-8',
            errors='replace',
            timeout=timeout,
            cwd=temp_dir
        )
        
        if result.returncode == 0:
            return True, result.stdout.strip(), None
        else:
            return False, None, result.stderr.strip()
    
    except subprocess.TimeoutExpired:
        return False, None, "Timeout"
    except Exception as e:
        return False, None, str(e)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def evaluate_functional_correctness(
    model,
    tokenizer,
    java_data,
    csharp_data,
    device: str,
    num_samples: int = None,
    use_post_process: bool = True,
) -> dict:
    """
    Evaluate functional correctness of translated code
    
    Determine correctness by comparing the execution output of translated code with reference code
    """
    samples = list(zip(java_data, csharp_data))
    if num_samples:
        samples = samples[:num_samples]
    
    total = len(samples)
    compiled = 0
    output_matched = 0
    results = []
    
    processor = PostProcessor(use_formatting=True, use_healing=True) if use_post_process else None
    
    print(f"\nEvaluating {total} samples...")
    
    for i, (java_item, csharp_item) in enumerate(tqdm(samples, desc="Functional Test")):
        java_code = java_item['code']
        reference_csharp = csharp_item['code']
        
        # 1. Run reference C# code to get expected output
        ref_success, ref_output, ref_error = run_csharp_code(reference_csharp)
        
        if not ref_success:
            # Reference code failed to run, skip
            results.append({
                "index": i,
                "status": "ref_failed",
                "ref_error": ref_error,
            })
            continue
        
        # 2. Translate Java code
        translated = generate_translation(model, tokenizer, java_code, device)
        
        # 3. Post-processing (if enabled)
        if processor:
            translated = processor.process(translated)
        
        # 4. Run translated code
        trans_success, trans_output, trans_error = run_csharp_code(translated)
        
        if trans_success:
            compiled += 1
            
            # 5. Compare output
            if trans_output == ref_output:
                output_matched += 1
                status = "passed"
            else:
                status = "output_mismatch"
        else:
            status = "compile_failed"
        
        results.append({
            "index": i,
            "status": status,
            "java_code_preview": java_code[:200],
            "translated_preview": translated[:200],
            "ref_output": ref_output,
            "trans_output": trans_output if trans_success else None,
            "trans_error": trans_error if not trans_success else None,
        })
    
    # Calculate valid samples (excluding those where reference code failed)
    valid_samples = sum(1 for r in results if r["status"] != "ref_failed")
    
    return {
        "pass_rate": output_matched / valid_samples if valid_samples > 0 else 0,
        "compilation_rate": compiled / valid_samples if valid_samples > 0 else 0,
        "passed": output_matched,
        "compiled": compiled,
        "valid_samples": valid_samples,
        "total_samples": total,
        "ref_failed": total - valid_samples,
        "detailed_results": results,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate Java→C# translation functional correctness (Code-to-Code)"
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
    parser.add_argument(
        "--no-post-process",
        action="store_true",
        help="Disable post-processing"
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("=" * 60)
    print("Code-to-Code Functional Correctness Test")
    print("Java → C# Translation Functional Correctness")
    print("=" * 60)
    
    # Environment Check
    print("\n[1] Environment Check")
    
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"  Device: {device}")
    
    if not check_dotnet_available():
        print("  ✗ .NET SDK not available, cannot run functional tests")
        print("  Please install .NET 8.0 SDK: https://dotnet.microsoft.com/download")
        return
    print("  ✓ .NET SDK available")
    
    # Load Dataset
    print("\n[2] Load Aligned Dataset")
    try:
        java_data = load_dataset(
            "json",
            data_files={"test": "xlcost_data/data/aligned/java_aligned.json"},
            split="test"
        )
        csharp_data = load_dataset(
            "json",
            data_files={"test": "xlcost_data/data/aligned/csharp_aligned.json"},
            split="test"
        )
    except Exception as e:
        print(f"  ✗ Dataset load failed: {e}")
        return
    
    print(f"  ✓ Loaded {len(java_data)} aligned samples")
    
    # Load Model
    print("\n[3] Load Model")
    ft_tokenizer, ft_model = load_model(args.fine_tuned_path, device)
    if ft_model is None:
        print("  ✗ Fine-tuned model load failed")
        return
    print("  ✓ Fine-tuned model loaded successfully")
    
    base_tokenizer, base_model = None, None
    if args.compare_base:
        base_tokenizer, base_model = load_model(BASE_MODEL_NAME, device)
        if base_model:
            print("  ✓ Base model loaded successfully")
    
    # Results
    results = {
        "timestamp": datetime.now().isoformat(),
        "task": "java-to-csharp-functional-correctness",
        "num_samples": args.num_samples or len(java_data),
        "device": device,
        "post_process_enabled": not args.no_post_process,
    }
    
    # Evaluate Fine-tuned Model
    print("\n[4] Evaluate Fine-tuned Model")
    ft_results = evaluate_functional_correctness(
        ft_model, ft_tokenizer,
        java_data, csharp_data,
        device,
        num_samples=args.num_samples,
        use_post_process=not args.no_post_process,
    )
    results["fine_tuned"] = {
        "model": args.fine_tuned_path,
        "pass_rate": ft_results["pass_rate"],
        "compilation_rate": ft_results["compilation_rate"],
        "passed": ft_results["passed"],
        "compiled": ft_results["compiled"],
        "valid_samples": ft_results["valid_samples"],
        "total_samples": ft_results["total_samples"],
    }
    
    # Evaluate Base Model
    if args.compare_base and base_model:
        print("\n[5] Evaluate Base Model")
        base_results = evaluate_functional_correctness(
            base_model, base_tokenizer,
            java_data, csharp_data,
            device,
            num_samples=args.num_samples,
            use_post_process=not args.no_post_process,
        )
        results["base"] = {
            "model": BASE_MODEL_NAME,
            "pass_rate": base_results["pass_rate"],
            "compilation_rate": base_results["compilation_rate"],
            "passed": base_results["passed"],
            "compiled": base_results["compiled"],
            "valid_samples": base_results["valid_samples"],
            "total_samples": base_results["total_samples"],
        }
    
    # Save Results
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved: {args.output}")
    
    # Print Report
    print("\n" + "=" * 60)
    print("Evaluation Report")
    print("=" * 60)
    print(f"Task: Java → C# Translation")
    print(f"Valid Samples: {ft_results['valid_samples']} (Ref Failed: {ft_results['ref_failed']})")
    print()
    
    print("【Fine-tuned Model】")
    print(f"  Pass Rate: {ft_results['pass_rate']:.2%}")
    print(f"  Compilation Rate: {ft_results['compilation_rate']:.2%}")
    print(f"  Passed Tests: {ft_results['passed']}/{ft_results['valid_samples']}")
    
    if args.compare_base and base_model:
        print("\n【Base Model】")
        print(f"  Pass Rate: {base_results['pass_rate']:.2%}")
        print(f"  Compilation Rate: {base_results['compilation_rate']:.2%}")
        print(f"  Passed Tests: {base_results['passed']}/{base_results['valid_samples']}")
        
        print("\n【Comparison】")
        improvement = ft_results["pass_rate"] - base_results["pass_rate"]
        print(f"  Pass Rate Improvement: {'+' if improvement >= 0 else ''}{improvement:.2%}")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
