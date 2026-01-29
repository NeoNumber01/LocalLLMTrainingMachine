# -*- coding: utf-8 -*-
"""
Unit Test Pass Rate Evaluation Module
Evaluates functional correctness of generated code using MultiPL-E dataset (HumanEval-CS / MBPP-CS)

MultiPL-E is a scalable and polyglot approach to benchmarking neural code generation.
Each sample contains:
- prompt: Function signature and docstring
- tests: Unit test code
- canonical_solution: Reference solution

Reference: "MultiPL-E: A Scalable and Polyglot Approach to Benchmarking Neural Code Generation"
"""

from typing import List, Tuple, Dict, Any, Optional
import subprocess
import tempfile
import os
import re
import json
from datetime import datetime

# .NET Project Template (for running tests)
CSPROJ_TEMPLATE = """<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net8.0</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>
    <Nullable>enable</Nullable>
    <NoWarn>CS8019;CS0169;CS0649;CS0414;CS8618;CS8600;CS8601;CS8602;CS8603;CS8604</NoWarn>
  </PropertyGroup>
</Project>"""

# Basic using statements
USING_STATEMENTS = """using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Diagnostics;

"""


def check_dotnet_available() -> bool:
    """Check if .NET SDK is installed"""
    try:
        result = subprocess.run(
            ["dotnet", "--version"],
            capture_output=True,
            encoding='utf-8',
            errors='replace',
            timeout=10
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def load_multipl_e_dataset(subset: str = "humaneval-cs", split: str = "test"):
    """
    Load MultiPL-E dataset
    
    Args:
        subset: Dataset subset ("humaneval-cs" or "mbpp-cs")
        split: Data split ("test")
    
    Returns:
        Dataset object
    """
    try:
        from datasets import load_dataset
        ds = load_dataset("nuprl/MultiPL-E", subset, split=split)
        return ds
    except Exception as e:
        print(f"Error loading MultiPL-E dataset: {e}")
        print("Please ensure datasets library is installed: pip install datasets")
        return None


def extract_function_name(prompt: str) -> Optional[str]:
    """Extract function name from prompt"""
    # C# function signature pattern: public static <type> FunctionName(...)
    patterns = [
        r'public\s+static\s+\w+\s+(\w+)\s*\(',
        r'public\s+\w+\s+(\w+)\s*\(',
        r'static\s+\w+\s+(\w+)\s*\(',
    ]
    for pattern in patterns:
        match = re.search(pattern, prompt)
        if match:
            return match.group(1)
    return None


def prepare_test_code(generated_code: str, tests: str, prompt: str = "") -> str:
    """
    Prepare executable test code
    
    MultiPL-E format description:
    - prompt: Contains using statements, class definition, function signature (empty body)
    - solution/generated_code: Function body implementation
    - tests: Starts with '}' to close function, then Main method and assertions
    
    Correct concatenation: prompt + solution + tests
    
    Example:
    prompt: "using System; ... class Problem { public static bool Func(int x) {"
    solution: "return x > 0;"  
    tests: "}\n public static void Main(string[] args) { Debug.Assert(...); }\n}"
    """
    # MultiPL-E prompt already contains valid using and class structure
    # Direct concatenation: prompt + generated body + tests (close function + Main)
    
    code_body = generated_code.strip()
    
    # Ensure generated code doesn't repeat prompt content
    # Some models might regenerate the prompt
    if prompt and code_body.startswith(prompt.strip()[:50]):
        # If generated code starts with prompt, extract the body
        code_body = code_body[len(prompt):].strip()
    
    # Concatenate full code
    full_code = prompt + code_body + tests
    
    return full_code


def run_unit_tests(
    generated_code: str,
    tests: str,
    prompt: str = "",
    timeout: int = 30
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Run unit tests
    
    Args:
        generated_code: Model generated code
        tests: Test code provided by MultiPL-E
        prompt: Original prompt (for debugging)
        timeout: Execution timeout (seconds)
    
    Returns:
        Tuple[bool, str, Dict]:
            - passed: Whether all tests passed
            - message: Result message
            - details: Detailed info
    """
    if not check_dotnet_available():
        return False, "dotnet SDK not available", {"error": "dotnet_unavailable"}
    
    details = {
        "compilation_success": False,
        "execution_success": False,
        "output": "",
        "error": "",
    }
    
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            # Write project file
            csproj_path = os.path.join(tmpdir, "Test.csproj")
            with open(csproj_path, "w", encoding="utf-8") as f:
                f.write(CSPROJ_TEMPLATE)
            
            # Prepare test code
            full_code = prepare_test_code(generated_code, tests, prompt)
            
            # Write code file
            cs_path = os.path.join(tmpdir, "Program.cs")
            with open(cs_path, "w", encoding="utf-8") as f:
                f.write(full_code)
            
            details["full_code"] = full_code[:2000]  # Keep first 2000 chars for debugging
            
            # Compile and run
            result = subprocess.run(
                ["dotnet", "run", "--nologo"],
                cwd=tmpdir,
                capture_output=True,
                encoding='utf-8',
                errors='replace',
                timeout=timeout
            )
            
            details["output"] = result.stdout[:500] if result.stdout else ""
            details["error"] = result.stderr[:500] if result.stderr else ""
            
            if result.returncode == 0:
                details["compilation_success"] = True
                details["execution_success"] = True
                return True, "All tests passed", details
            else:
                # Check if compilation error or runtime error
                if "error CS" in (result.stderr or "") or "error CS" in (result.stdout or ""):
                    details["compilation_success"] = False
                    return False, "Compilation failed", details
                else:
                    details["compilation_success"] = True
                    details["execution_success"] = False
                    return False, "Tests failed (assertion or runtime error)", details
                    
        except subprocess.TimeoutExpired:
            return False, "Execution timeout", {"error": "timeout", "timeout_seconds": timeout}
        except Exception as e:
            return False, f"Execution error: {str(e)}", {"error": str(e)}


def evaluate_unit_test_pass_rate(
    model,
    tokenizer,
    dataset,
    device: str = "cuda",
    num_samples: Optional[int] = None,
    verbose: bool = True
) -> Dict[str, Any]:
    """
    Evaluate unit test pass rate on MultiPL-E dataset
    
    Args:
        model: Model to evaluate
        tokenizer: Corresponding tokenizer
        dataset: MultiPL-E dataset
        device: Device to run on
        num_samples: Number of samples to evaluate (None for all)
        verbose: Whether to print detailed info
    
    Returns:
        Evaluation results dictionary
    """
    import torch
    from tqdm import tqdm
    
    if dataset is None:
        return {"error": "Dataset not loaded", "pass_at_1": 0.0}
    
    results = {
        "pass_at_1": 0.0,
        "tests_passed": 0,
        "tests_total": 0,
        "compilation_rate": 0.0,
        "compiled_count": 0,
        "sample_results": [],
        "timestamp": datetime.now().isoformat(),
    }
    
    samples = list(dataset)
    if num_samples:
        samples = samples[:num_samples]
    
    results["tests_total"] = len(samples)
    passed_count = 0
    compiled_count = 0
    
    for i, sample in enumerate(tqdm(samples, desc="Evaluating unit tests")):
        prompt = sample.get("prompt", "")
        tests = sample.get("tests", "")
        canonical = sample.get("canonical_solution", "")
        
        # Generate code
        try:
            # Construct input (adapt to CodeT5 input format)
            # Note: Adjust prompt format according to your model
            input_text = f"Complete the following C# function:\n{prompt}"
            
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
                    pad_token_id=tokenizer.pad_token_id,
                )
            
            generated_code = tokenizer.decode(output[0], skip_special_tokens=True)
            
        except Exception as e:
            if verbose:
                print(f"  [{i+1}] ✗ Generation error: {e}")
            results["sample_results"].append({
                "index": i,
                "passed": False,
                "error": f"generation_error: {str(e)}"
            })
            continue
        
        # Run tests
        passed, message, details = run_unit_tests(generated_code, tests, prompt)
        
        if details.get("compilation_success", False):
            compiled_count += 1
        
        if passed:
            passed_count += 1
            if verbose:
                print(f"  [{i+1}/{len(samples)}] ✓ Passed")
        else:
            if verbose:
                print(f"  [{i+1}/{len(samples)}] ✗ {message}")
        
        # Record sample results (keep only first 50 detailed results)
        if len(results["sample_results"]) < 50:
            results["sample_results"].append({
                "index": i,
                "passed": passed,
                "message": message,
                "generated_code_preview": generated_code[:200] if generated_code else "",
                "prompt_preview": prompt[:100] if prompt else "",
            })
    
    # Calculate final metrics
    total = results["tests_total"]
    results["tests_passed"] = passed_count
    results["pass_at_1"] = passed_count / total if total > 0 else 0.0
    results["compiled_count"] = compiled_count
    results["compilation_rate"] = compiled_count / total if total > 0 else 0.0
    
    return results


def run_canonical_solution_test(dataset, num_samples: int = 5, verbose: bool = True) -> Dict:
    """
    Verify test environment correctness
    
    Note: MultiPL-E dataset does not contain canonical_solution field!
    So we use manually written test code to verify if .NET environment is normal.
    
    Args:
        dataset: MultiPL-E dataset
        num_samples: Number of samples to test
        verbose: Whether to print detailed info
    
    Returns:
        Test results
    """
    if verbose:
        print("\nVerifying test environment...")
    
    # Check if dataset contains canonical_solution
    if dataset is not None and len(dataset) > 0:
        sample = dataset[0]
        has_canonical = bool(sample.get("canonical_solution", "").strip())
        
        if not has_canonical:
            if verbose:
                print("  ⚠️ MultiPL-E dataset does not contain canonical_solution field")
                print("  Using manual test to verify .NET environment...")
    
    # Manual test: Verify .NET compilation and execution environment
    test_code = """using System;
using System.Collections.Generic;
using System.Diagnostics;

class TestEnvironment {
    public static int Add(int a, int b) {
        return a + b;
    }
    public static void Main(string[] args) {
        Debug.Assert(Add(2, 3) == 5);
        Debug.Assert(Add(-1, 1) == 0);
        Console.WriteLine("Environment test passed!");
    }
}
"""
    
    # Run test directly (not via prepare_test_code)
    import tempfile
    import os
    
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            csproj_path = os.path.join(tmpdir, "Test.csproj")
            with open(csproj_path, "w", encoding="utf-8") as f:
                f.write(CSPROJ_TEMPLATE)
            
            cs_path = os.path.join(tmpdir, "Program.cs")
            with open(cs_path, "w", encoding="utf-8") as f:
                f.write(test_code)
            
            result = subprocess.run(
                ["dotnet", "run", "--nologo"],
                cwd=tmpdir,
                capture_output=True,
                encoding='utf-8',
                errors='replace',
                timeout=60
            )
            
            env_ok = result.returncode == 0
            
            if verbose:
                if env_ok:
                    print("  ✓ .NET runtime environment normal")
                else:
                    print("  ✗ .NET runtime environment abnormal")
                    print(f"    Error: {result.stderr[:200] if result.stderr else result.stdout[:200]}")
            
            return {
                "environment_ok": env_ok,
                "canonical_pass_rate": 1.0 if env_ok else 0.0,
                "passed": 1 if env_ok else 0,
                "total": 1,
                "note": "MultiPL-E does not include canonical_solution; using environment test only",
            }
            
        except Exception as e:
            if verbose:
                print(f"  ✗ Environment test failed: {e}")
            return {
                "environment_ok": False,
                "canonical_pass_rate": 0.0,
                "passed": 0,
                "total": 1,
                "error": str(e),
            }


if __name__ == "__main__":
    print("=" * 60)
    print("Unit Test Pass Rate Evaluation Module Test")
    print("=" * 60)
    
    # Check Environment
    print("\n[1] Checking .NET SDK:")
    if check_dotnet_available():
        print("  ✓ .NET SDK available")
    else:
        print("  ✗ .NET SDK unavailable, please install .NET 8.0 SDK")
        exit(1)
    
    # Load Dataset
    print("\n[2] Loading MultiPL-E Dataset (humaneval-cs):")
    try:
        ds = load_multipl_e_dataset("humaneval-cs")
        if ds:
            print(f"  ✓ Successfully loaded {len(ds)} samples")
            
            # Show sample structure
            print("\n[3] Sample Structure Example:")
            sample = ds[0]
            print(f"  Keys: {list(sample.keys())}")
            print(f"  Prompt preview: {sample.get('prompt', '')[:100]}...")
            print(f"  Tests preview: {sample.get('tests', '')[:100]}...")
            
            # Verify canonical solution
            print("\n[4] Verifying Canonical Solution:")
            canonical_result = run_canonical_solution_test(ds, num_samples=3, verbose=True)
            print(f"\n  Canonical Pass Rate: {canonical_result['canonical_pass_rate']:.2%}")
            
        else:
            print("  ✗ Dataset load failed")
    except Exception as e:
        print(f"  ✗ Error: {e}")
        print("  Please run: pip install datasets")
