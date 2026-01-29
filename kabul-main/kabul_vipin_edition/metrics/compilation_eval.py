# -*- coding: utf-8 -*-
"""
Compilation Success Rate Evaluation Module
Uses dotnet build to verify generated C# code syntax correctness
"""

import subprocess
import tempfile
import os
import shutil
from typing import List, Tuple, Dict, Any


# .NET Project Template
CSPROJ_TEMPLATE = """<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Library</OutputType>
    <TargetFramework>net8.0</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>
    <Nullable>enable</Nullable>
    <NoWarn>CS8019;CS0169;CS0649;CS0414;CS8618</NoWarn>
  </PropertyGroup>
</Project>"""

# Basic using statements, ensuring common types are available
USING_STATEMENTS = """using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;

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


def check_compilation(code: str, include_usings: bool = True) -> Tuple[bool, str]:
    """
    Check if single C# code snippet compiles successfully
    
    Args:
        code: C# code string
        include_usings: Whether to automatically add using statements
    
    Returns:
        (compiled_successfully, error_message_or_empty)
    """
    if not check_dotnet_available():
        return False, "dotnet SDK not available"
    
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            # Write project file
            csproj_path = os.path.join(tmpdir, "Test.csproj")
            with open(csproj_path, "w", encoding="utf-8") as f:
                f.write(CSPROJ_TEMPLATE)
            
            # Prepare code (add using statements)
            full_code = (USING_STATEMENTS + code) if include_usings else code
            
            # Write code file
            cs_path = os.path.join(tmpdir, "Code.cs")
            with open(cs_path, "w", encoding="utf-8") as f:
                f.write(full_code)
            
            # Execute build (includes restore)
            result = subprocess.run(
                ["dotnet", "build", "--nologo", "-v", "q"],
                cwd=tmpdir,
                capture_output=True,
                encoding='utf-8',
                errors='replace',
                timeout=60
            )
            
            if result.returncode == 0:
                return True, ""
            else:
                # Extract error message
                error_msg = result.stderr.strip() or result.stdout.strip()
                # Keep only first 500 chars of error
                return False, error_msg[:500] if len(error_msg) > 500 else error_msg
                
        except subprocess.TimeoutExpired:
            return False, "Compilation timeout"
        except Exception as e:
            return False, f"Compilation failed: {str(e)}"


def calculate_compilation_rate(
    predictions: List[str],
    verbose: bool = False
) -> Dict[str, Any]:
    """
    Calculate compilation rate for a batch of code
    
    Args:
        predictions: List of model-generated code
        verbose: Whether to print detailed info
    
    Returns:
        Dictionary containing compilation rate and detailed results
    """
    if not check_dotnet_available():
        return {
            "compilation_rate": -1.0,
            "compiled": 0,
            "total": len(predictions),
            "error": "dotnet SDK not available"
        }
    
    compiled_count = 0
    errors = []
    
    for i, code in enumerate(predictions):
        success, error_msg = check_compilation(code)
        if success:
            compiled_count += 1
            if verbose:
                print(f"  [{i+1}/{len(predictions)}] ✓ Compilation Successful")
        else:
            errors.append({"index": i, "error": error_msg})
            if verbose:
                print(f"  [{i+1}/{len(predictions)}] ✗ Compilation Failed: {error_msg[:100]}...")
    
    rate = compiled_count / len(predictions) if predictions else 0.0
    
    return {
        "compilation_rate": rate,
        "compiled": compiled_count,
        "total": len(predictions),
        "failed_samples": errors[:10]  # Keep only first 10 error details
    }


def check_compilation_with_wrapper(code: str) -> Tuple[bool, str]:
    """
    Try compiling with wrapper class (suitable for method-only code)
    
    Args:
        code: C# code string
    
    Returns:
        (compiled_successfully, error_message_or_empty)
    """
    # Try compiling directly first
    success, error = check_compilation(code)
    if success:
        return True, ""
    
    # If failed, try wrapping in a class
    wrapped_code = f"""
public class TestWrapper {{
    {code}
}}
"""
    success, error = check_compilation(wrapped_code)
    if success:
        return True, ""
    
    # Try wrapping in static class
    static_wrapped = f"""
public static class TestWrapper {{
    {code}
}}
"""
    return check_compilation(static_wrapped)


if __name__ == "__main__":
    # Quick Test
    print("Check .NET SDK availability:", check_dotnet_available())
    
    test_codes = [
        # Correct code
        "public class Test { public void Hello() { Console.WriteLine(\"Hi\"); } }",
        # Code with syntax error
        "public class Test { public void Hello( { Console.WriteLine(\"Hi\"); } }",
        # Code using LINQ
        "public class Test { public int[] GetEven(int[] arr) { return arr.Where(x => x % 2 == 0).ToArray(); } }",
    ]
    
    print("\nCompilation Test:")
    for i, code in enumerate(test_codes):
        success, error = check_compilation(code)
        status = "✓" if success else "✗"
        print(f"  [{i+1}] {status} {code[:50]}...")
        if error:
            print(f"      Error: {error[:100]}")
    
    print("\nBatch Compilation Rate:")
    result = calculate_compilation_rate(test_codes, verbose=True)
    print(f"  Compilation Rate: {result['compilation_rate']:.2%}")
