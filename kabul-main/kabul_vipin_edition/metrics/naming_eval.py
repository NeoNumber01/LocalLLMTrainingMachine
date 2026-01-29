# -*- coding: utf-8 -*-
"""
C# Naming Convention Evaluation Module
Detects if generated code follows C# naming conventions
"""

import re
from typing import List, Dict, Any


def is_pascal_case(name: str) -> bool:
    """Check if name is PascalCase"""
    if not name:
        return False
    # First letter upper, no underscores (unless all upper, handled elsewhere)
    return name[0].isupper() and '_' not in name


def is_camel_case(name: str) -> bool:
    """Check if name is camelCase"""
    if not name:
        return False
    return name[0].islower() and '_' not in name


def is_upper_snake_case(name: str) -> bool:
    """Check if name is UPPER_SNAKE_CASE (Java constant style)"""
    if not name:
        return False
    return name.isupper() and '_' in name


def check_naming_conventions(code: str) -> Dict[str, Any]:
    """
    Detect C# Naming Convention Compliance
    
    C# Naming Conventions:
    - Method: PascalCase
    - Class: PascalCase
    - Interface: I-prefix + PascalCase
    - Local Variable: camelCase
    - Field: _camelCase (private) or PascalCase (public)
    - Constant: PascalCase (not UPPER_SNAKE_CASE)
    
    Args:
        code: C# code string
    
    Returns:
        Naming convention statistics dictionary
    """
    results = {
        "methods": {"total": 0, "pascal_case": 0},
        "classes": {"total": 0, "pascal_case": 0},
        "interfaces": {"total": 0, "i_prefix": 0},
        "variables": {"total": 0, "camel_case": 0},
        "constants": {"total": 0, "pascal_case": 0, "upper_snake": 0},
    }
    
    # Detect Method Names (Should be PascalCase)
    # Match: public void MethodName(
    method_pattern = r'(?:public|private|protected|internal|static|\s)+\s+(?:\w+(?:<[^>]+>)?)\s+(\w+)\s*\('
    methods = re.findall(method_pattern, code)
    results["methods"]["total"] = len(methods)
    results["methods"]["pascal_case"] = sum(1 for m in methods if is_pascal_case(m))
    
    # Detect Class Names (Should be PascalCase)
    class_pattern = r'\bclass\s+(\w+)'
    classes = re.findall(class_pattern, code)
    results["classes"]["total"] = len(classes)
    results["classes"]["pascal_case"] = sum(1 for c in classes if is_pascal_case(c))
    
    # Detect Interface Names (Should be I-prefix + PascalCase)
    interface_pattern = r'\binterface\s+(\w+)'
    interfaces = re.findall(interface_pattern, code)
    results["interfaces"]["total"] = len(interfaces)
    results["interfaces"]["i_prefix"] = sum(
        1 for i in interfaces if i.startswith('I') and len(i) > 1 and i[1].isupper()
    )
    
    # Detect Local Variables (Should be camelCase)
    # Simple detection: var xxx = or Type xxx =
    var_pattern = r'(?:var|int|string|float|double|bool|long|char)\s+(\w+)\s*='
    variables = re.findall(var_pattern, code)
    results["variables"]["total"] = len(variables)
    results["variables"]["camel_case"] = sum(1 for v in variables if is_camel_case(v))
    
    # Detect Constants (C# should be PascalCase, Java is UPPER_SNAKE_CASE)
    const_pattern = r'\bconst\s+\w+\s+(\w+)\s*='
    constants = re.findall(const_pattern, code)
    results["constants"]["total"] = len(constants)
    results["constants"]["pascal_case"] = sum(1 for c in constants if is_pascal_case(c))
    results["constants"]["upper_snake"] = sum(1 for c in constants if is_upper_snake_case(c))
    
    # Calculate Overall Score
    results["overall_score"] = calculate_naming_score(results)
    
    return results


def calculate_naming_score(stats: Dict[str, Any]) -> float:
    """
    Calculate overall score based on naming checks
    
    Args:
        stats: Statistics dictionary from check_naming_conventions
    
    Returns:
        Naming convention score (0-1)
    """
    total_checked = 0
    total_correct = 0
    
    # Method names have highest weight
    if stats["methods"]["total"] > 0:
        total_checked += stats["methods"]["total"] * 2  # Weight 2
        total_correct += stats["methods"]["pascal_case"] * 2
    
    # Class names
    if stats["classes"]["total"] > 0:
        total_checked += stats["classes"]["total"]
        total_correct += stats["classes"]["pascal_case"]
    
    # Interface names
    if stats["interfaces"]["total"] > 0:
        total_checked += stats["interfaces"]["total"]
        total_correct += stats["interfaces"]["i_prefix"]
    
    # Variable names
    if stats["variables"]["total"] > 0:
        total_checked += stats["variables"]["total"]
        total_correct += stats["variables"]["camel_case"]
    
    # Constants (If UPPER_SNAKE_CASE used, it implies Java style)
    if stats["constants"]["total"] > 0:
        total_checked += stats["constants"]["total"]
        total_correct += stats["constants"]["pascal_case"]
    
    if total_checked == 0:
        return 1.0  # No checkable names found
    
    return total_correct / total_checked


def calculate_batch_naming_stats(predictions: List[str]) -> Dict[str, Any]:
    """
    Calculate naming statistics for a batch of code
    
    Args:
        predictions: List of code strings
    
    Returns:
        Summary statistics dictionary
    """
    all_scores = []
    total_stats = {
        "methods": {"total": 0, "pascal_case": 0},
        "classes": {"total": 0, "pascal_case": 0},
        "interfaces": {"total": 0, "i_prefix": 0},
        "variables": {"total": 0, "camel_case": 0},
        "constants": {"total": 0, "pascal_case": 0, "upper_snake": 0},
    }
    
    for code in predictions:
        stats = check_naming_conventions(code)
        all_scores.append(stats["overall_score"])
        
        # Accumulate stats
        for category in total_stats.keys():
            for key in total_stats[category].keys():
                total_stats[category][key] += stats[category][key]
    
    avg_score = sum(all_scores) / len(all_scores) if all_scores else 0.0
    
    return {
        "average_naming_score": avg_score,
        "total_stats": total_stats,
        "samples_analyzed": len(predictions)
    }


def detect_java_naming_violations(code: str) -> List[str]:
    """
    Detect Java-style naming violations in code
    
    Args:
        code: C# code string
    
    Returns:
        List of violation descriptions
    """
    violations = []
    
    # Detect camelCase method names (Java style)
    method_pattern = r'(?:public|private|protected|internal|static|\s)+\s+\w+\s+([a-z]\w*)\s*\('
    methods = re.findall(method_pattern, code)
    camel_methods = [m for m in methods if is_camel_case(m) and m not in ['main', 'if', 'for', 'while']]
    if camel_methods:
        violations.append(f"camelCase method name (Should be PascalCase): {camel_methods[:3]}")
    
    # Detect UPPER_SNAKE_CASE constants (Java style)
    const_pattern = r'\bconst\s+\w+\s+([A-Z][A-Z_0-9]+)\s*='
    upper_snake_consts = re.findall(const_pattern, code)
    if upper_snake_consts:
        violations.append(f"UPPER_SNAKE_CASE constant (Should be PascalCase): {upper_snake_consts[:3]}")
    
    # Detect Interface without I-prefix
    interface_pattern = r'\binterface\s+([A-Z][a-z]\w*)'
    no_i_interfaces = [i for i in re.findall(interface_pattern, code) if not i.startswith('I')]
    if no_i_interfaces:
        violations.append(f"Interface missing I-prefix: {no_i_interfaces[:3]}")
    
    return violations


if __name__ == "__main__":
    # Test Code
    csharp_style = """
    public interface IRepository {
        void SaveData();
    }
    
    public class DataService {
        private const int MaxRetries = 3;
        
        public void ProcessData() {
            var itemCount = 0;
            var userName = "test";
        }
    }
    """
    
    java_style = """
    public interface Repository {
        void saveData();
    }
    
    public class DataService {
        private static final int MAX_RETRIES = 3;
        
        public void processData() {
            int itemCount = 0;
            String userName = "test";
        }
    }
    """
    
    print("=== C# Style Code ===")
    result = check_naming_conventions(csharp_style)
    print(f"  Methods: {result['methods']['pascal_case']}/{result['methods']['total']} PascalCase")
    print(f"  Classes: {result['classes']['pascal_case']}/{result['classes']['total']} PascalCase")
    print(f"  Interfaces: {result['interfaces']['i_prefix']}/{result['interfaces']['total']} I-prefix")
    print(f"  Overall Score: {result['overall_score']:.2%}")
    
    print("\n=== Java Style Code ===")
    result = check_naming_conventions(java_style)
    print(f"  Methods: {result['methods']['pascal_case']}/{result['methods']['total']} PascalCase")
    print(f"  Classes: {result['classes']['pascal_case']}/{result['classes']['total']} PascalCase")
    print(f"  Interfaces: {result['interfaces']['i_prefix']}/{result['interfaces']['total']} I-prefix")
    print(f"  Overall Score: {result['overall_score']:.2%}")
    
    violations = detect_java_naming_violations(java_style)
    if violations:
        print("  Java style violations found:")
        for v in violations:
            print(f"    - {v}")
