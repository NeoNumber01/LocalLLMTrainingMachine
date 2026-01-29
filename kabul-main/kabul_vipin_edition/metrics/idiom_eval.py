# -*- coding: utf-8 -*-
"""
C# Idiom Detection Module
Detects the frequency of C# specific idioms in generated code
"""

import re
from typing import List, Dict, Any


# C# Idiom Patterns
CSHARP_IDIOMS = {
    # LINQ Method Chain
    "linq": [
        r'\.Where\s*\(',
        r'\.Select\s*\(',
        r'\.Any\s*\(',
        r'\.All\s*\(',
        r'\.OrderBy\s*\(',
        r'\.OrderByDescending\s*\(',
        r'\.FirstOrDefault\s*\(',
        r'\.First\s*\(',
        r'\.LastOrDefault\s*\(',
        r'\.Last\s*\(',
        r'\.Single\s*\(',
        r'\.SingleOrDefault\s*\(',
        r'\.Count\s*\(',
        r'\.Sum\s*\(',
        r'\.Average\s*\(',
        r'\.Max\s*\(',
        r'\.Min\s*\(',
        r'\.Take\s*\(',
        r'\.Skip\s*\(',
        r'\.ToList\s*\(',
        r'\.ToArray\s*\(',
        r'\.ToDictionary\s*\(',
        r'\.GroupBy\s*\(',
        r'\.Join\s*\(',
        r'\.Distinct\s*\(',
        r'\.Aggregate\s*\(',
    ],
    
    # var keyword
    "var_keyword": [
        r'\bvar\s+\w+\s*=',
    ],
    
    # foreach loop
    "foreach": [
        r'\bforeach\s*\(',
    ],
    
    # Auto-Implemented Properties
    "auto_properties": [
        r'\{\s*get\s*;\s*set\s*;\s*\}',
        r'\{\s*get\s*;\s*\}',
        r'\{\s*get\s*;\s*private\s+set\s*;\s*\}',
    ],
    
    # Null Conditional Operators
    "null_conditional": [
        r'\?\.',         # null propagation
        r'\?\[',         # null index
        r'\?\?',         # null coalescing
        r'\?\?=',        # null coalescing assignment
    ],
    
    # String Interpolation
    "string_interpolation": [
        r'\$"[^"]*\{',   # Interpolated string
        r'\$@"[^"]*\{',  # Verbatim interpolated string
    ],
    
    # Expression Bodied (=>)
    "expression_bodied": [
        r'=>\s*[^;]+;',  # Expression bodied method/property
    ],
    
    # using statement
    "using_statement": [
        r'\busing\s*\([^)]+\)\s*\{',  # using block
        r'\busing\s+var\s+',           # using declaration
    ],
    
    # async/await
    "async_await": [
        r'\basync\s+',
        r'\bawait\s+',
    ],
    
    # Pattern Matching
    "pattern_matching": [
        r'\bis\s+\w+\s+\w+',     # is pattern
        r'\bswitch\s*\(',        # switch expression
        r'\bwhen\s+',            # when clause
    ],
    
    # Tuples
    "tuples": [
        r'\([^)]+,\s*[^)]+\)\s*=',  # Tuple deconstruction
        r'<\([^)]+\)>',              # Tuple type
    ],
    
    # nameof operator
    "nameof": [
        r'\bnameof\s*\(',
    ],
    
    # Ranges and Indices
    "range_index": [
        r'\[\d*\.\.\d*\]',  # Range expression
        r'\[\^',            # End index
    ],
}

# Java Style Patterns (for contrast)
JAVA_PATTERNS = {
    "java_stream": [
        r'\.stream\s*\(',
        r'\.filter\s*\(',
        r'\.map\s*\(',
        r'\.collect\s*\(',
    ],
    "java_for_each": [
        r'\bfor\s*\(\s*\w+\s+\w+\s*:\s*',
    ],
    "java_optional": [
        r'Optional\.',
        r'\.orElse\s*\(',
        r'\.isPresent\s*\(',
    ],
}


def calculate_idiom_density(code: str) -> Dict[str, int]:
    """
    Calculate the occurrence count of various C# idioms in a single code snippet
    
    Args:
        code: C# code string
    
    Returns:
        Dictionary counting each idiom type
    """
    results = {}
    total_idioms = 0
    
    for idiom_type, patterns in CSHARP_IDIOMS.items():
        count = sum(len(re.findall(p, code, re.IGNORECASE)) for p in patterns)
        results[idiom_type] = count
        total_idioms += count
    
    results["total_idioms"] = total_idioms
    return results


def calculate_java_pattern_density(code: str) -> Dict[str, int]:
    """
    Detect residual Java style patterns in code
    
    Args:
        code: Code string
    
    Returns:
        Dictionary counting Java style patterns
    """
    results = {}
    total = 0
    
    for pattern_type, patterns in JAVA_PATTERNS.items():
        count = sum(len(re.findall(p, code, re.IGNORECASE)) for p in patterns)
        results[pattern_type] = count
        total += count
    
    results["total_java_patterns"] = total
    return results


def calculate_batch_idiom_stats(
    predictions: List[str]
) -> Dict[str, Any]:
    """
    Calculate idiom statistics for a batch of code
    
    Args:
        predictions: List of code strings
    
    Returns:
        Summary statistics dictionary
    """
    total_stats = {idiom: 0 for idiom in CSHARP_IDIOMS.keys()}
    total_stats["total_idioms"] = 0
    
    java_stats = {pat: 0 for pat in JAVA_PATTERNS.keys()}
    java_stats["total_java_patterns"] = 0
    
    for code in predictions:
        # C# Idioms
        idioms = calculate_idiom_density(code)
        for key, value in idioms.items():
            total_stats[key] = total_stats.get(key, 0) + value
        
        # Java Residual Patterns
        java = calculate_java_pattern_density(code)
        for key, value in java.items():
            java_stats[key] = java_stats.get(key, 0) + value
    
    # Calculate Averages
    n = len(predictions) if predictions else 1
    avg_stats = {f"avg_{k}": v / n for k, v in total_stats.items()}
    
    return {
        "csharp_idioms": total_stats,
        "java_patterns": java_stats,
        "averages": avg_stats,
        "samples_analyzed": len(predictions)
    }


def calculate_idiom_score(code: str) -> float:
    """
    Calculate idiom score (0-1)
    Higher score indicates code is more C#-style
    
    Args:
        code: C# code string
    
    Returns:
        Idiom score
    """
    csharp = calculate_idiom_density(code)
    java = calculate_java_pattern_density(code)
    
    csharp_count = csharp["total_idioms"]
    java_count = java["total_java_patterns"]
    
    total = csharp_count + java_count
    if total == 0:
        return 0.5  # Unable to judge
    
    # Score = C# Idiom Ratio
    return csharp_count / total


if __name__ == "__main__":
    # Test Code
    csharp_code = """
    public class Example {
        public int Id { get; set; }
        public string Name { get; set; }
        
        public void Process() {
            var items = GetItems();
            var filtered = items.Where(x => x > 0).Select(x => x * 2).ToList();
            
            foreach (var item in filtered) {
                Console.WriteLine($"Value: {item}");
            }
            
            var result = items?.FirstOrDefault() ?? 0;
        }
    }
    """
    
    java_style_code = """
    public class Example {
        public void process() {
            List<Integer> items = getItems();
            List<Integer> filtered = items.stream()
                .filter(x -> x > 0)
                .map(x -> x * 2)
                .collect(Collectors.toList());
            
            for (Integer item : filtered) {
                System.out.println("Value: " + item);
            }
        }
    }
    """
    
    print("=== C# Style Code ===")
    result = calculate_idiom_density(csharp_code)
    for k, v in result.items():
        if v > 0:
            print(f"  {k}: {v}")
    print(f"  Idiom Score: {calculate_idiom_score(csharp_code):.2%}")
    
    print("\n=== Java Style Code ===")
    result = calculate_idiom_density(java_style_code)
    print(f"  C# Idiom Total: {result['total_idioms']}")
    java_result = calculate_java_pattern_density(java_style_code)
    print(f"  Java Pattern Total: {java_result['total_java_patterns']}")
    print(f"  Idiom Score: {calculate_idiom_score(java_style_code):.2%}")
