#!/usr/bin/env python3
"""
Comprehensive Analysis of Split Datasets for LLM Training Pipeline
Focuses on: train_split.jsonl, test_split.jsonl, valid_split.jsonl
"""

import json
import os
import re
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from statistics import mean, median, stdev
from datetime import datetime

# Configuration
BASE_DIR = r"c:\Users\Shu Leo\Desktop\practical course\LLMTrainPipeline"
DATA_DIR = os.path.join(BASE_DIR, "backend", "storage", "final refined version")
OUTPUT_DIR = os.path.join(BASE_DIR, "backend", "docs")

SPLIT_DATASETS = {
    "train_split": os.path.join(DATA_DIR, "train_split.jsonl"),
    "test_split": os.path.join(DATA_DIR, "test_split.jsonl"),
    "valid_split": os.path.join(DATA_DIR, "valid_split.jsonl"),
}


def load_jsonl(path: str) -> list[dict]:
    """Load JSONL file and return list of entries"""
    entries = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def calculate_text_stats(texts: list[str]) -> dict:
    """Calculate comprehensive text statistics"""
    if not texts:
        return {}
    
    lengths = [len(t) for t in texts]
    word_counts = [len(t.split()) for t in texts]
    line_counts = [len(t.split('\n')) for t in texts]
    
    return {
        "count": len(texts),
        "char_length": {
            "min": min(lengths),
            "max": max(lengths),
            "mean": round(mean(lengths), 2),
            "median": round(median(lengths), 2),
            "std": round(stdev(lengths), 2) if len(lengths) > 1 else 0,
            "p25": sorted(lengths)[len(lengths)//4],
            "p75": sorted(lengths)[3*len(lengths)//4],
            "p95": sorted(lengths)[int(len(lengths)*0.95)],
        },
        "word_count": {
            "min": min(word_counts),
            "max": max(word_counts),
            "mean": round(mean(word_counts), 2),
            "median": round(median(word_counts), 2),
        },
        "line_count": {
            "min": min(line_counts),
            "max": max(line_counts),
            "mean": round(mean(line_counts), 2),
        }
    }


def infer_category(instruction: str) -> str:
    """Infer problem category from instruction text"""
    instruction_lower = instruction.lower()
    
    categories = {
        "file/io": ["file", "read", "write", "open", "close", "path", "directory", "folder", "csv", "json", "xml", "txt"],
        "list/array": ["list", "array", "element", "index", "append", "remove", "sort", "reverse", "slice"],
        "string": ["string", "character", "substring", "concatenate", "split", "join", "replace", "format", "text"],
        "math": ["number", "calculate", "sum", "product", "average", "mean", "median", "factorial", "prime", "fibonacci", "math"],
        "dictionary/map": ["dictionary", "dict", "key", "value", "hash", "map", "mapping"],
        "recursion": ["recursive", "recursion", "recur"],
        "sorting/searching": ["sort", "search", "binary search", "linear search", "bubble", "merge", "quick"],
        "tree/graph": ["tree", "graph", "node", "edge", "traverse", "bfs", "dfs", "binary tree"],
        "dynamic programming": ["dynamic programming", "dp", "memoization", "tabulation"],
        "algorithm": ["algorithm", "greedy", "backtracking", "divide and conquer"],
        "oop": ["class", "object", "inheritance", "polymorphism", "encapsulation"],
        "regex": ["regex", "regular expression", "pattern", "match"],
        "date/time": ["date", "time", "datetime", "timestamp", "calendar"],
        "api/web": ["api", "http", "request", "response", "url", "web"],
        "database": ["database", "sql", "query", "table", "record"],
    }
    
    for category, keywords in categories.items():
        if any(keyword in instruction_lower for keyword in keywords):
            return category
    
    return "other"


def analyze_test_cases(tests: str) -> dict:
    """Analyze test case structure and quality"""
    if not tests:
        return {"assertion_count": 0, "has_edge_cases": False, "test_types": []}
    
    assertion_count = tests.count("assert")
    
    # Detect test types
    test_types = []
    if "assert " in tests:
        test_types.append("assert_statement")
    if "assertEqual" in tests or "assertEquals" in tests:
        test_types.append("unittest_assert")
    if "pytest" in tests or "test_" in tests:
        test_types.append("pytest_style")
    
    # Detect edge cases
    edge_case_indicators = ["None", "[]", "{}", "''", '""', "0", "-1", "empty", "null", "boundary"]
    has_edge_cases = any(indicator in tests for indicator in edge_case_indicators)
    
    # Detect error handling tests
    has_error_tests = "raise" in tests or "Exception" in tests or "Error" in tests
    
    return {
        "assertion_count": assertion_count,
        "has_edge_cases": has_edge_cases,
        "has_error_tests": has_error_tests,
        "test_types": test_types,
        "line_count": len(tests.split('\n')),
    }


def analyze_reference_code(reference: str) -> dict:
    """Analyze reference solution code quality and characteristics"""
    if not reference:
        return {}
    
    lines = reference.split('\n')
    code_lines = [l for l in lines if l.strip() and not l.strip().startswith('#')]
    
    # Count imports
    imports = [l for l in lines if l.strip().startswith('import ') or l.strip().startswith('from ')]
    
    # Detect library usage
    libraries = []
    lib_patterns = [
        ("math", r'\bmath\b'),
        ("collections", r'\bcollections\b'),
        ("itertools", r'\bitertools\b'),
        ("functools", r'\bfunctools\b'),
        ("re", r'\bre\b'),
        ("os", r'\bos\b'),
        ("sys", r'\bsys\b'),
        ("json", r'\bjson\b'),
        ("datetime", r'\bdatetime\b'),
        ("random", r'\brandom\b'),
        ("typing", r'\btyping\b'),
        ("heapq", r'\bheapq\b'),
        ("bisect", r'\bbisect\b'),
    ]
    
    for lib_name, pattern in lib_patterns:
        if re.search(pattern, reference):
            libraries.append(lib_name)
    
    # Detect code patterns
    patterns = {
        "has_loops": bool(re.search(r'\b(for|while)\b', reference)),
        "has_recursion": bool(re.search(r'def\s+(\w+).*\1\s*\(', reference, re.DOTALL)),
        "has_comprehensions": bool(re.search(r'\[.+for.+in.+\]', reference)),
        "has_lambda": bool(re.search(r'\blambda\b', reference)),
        "has_try_except": bool(re.search(r'\btry\s*:', reference)),
        "has_class": bool(re.search(r'\bclass\s+\w+', reference)),
        "has_decorators": bool(re.search(r'@\w+', reference)),
        "has_type_hints": bool(re.search(r'->\s*\w+|:\s*\w+\s*=', reference)),
    }
    
    # Calculate complexity indicators
    nesting_level = max(len(line) - len(line.lstrip()) for line in code_lines) // 4 if code_lines else 0
    
    return {
        "total_lines": len(lines),
        "code_lines": len(code_lines),
        "import_count": len(imports),
        "libraries_used": libraries,
        "patterns": patterns,
        "max_nesting_level": nesting_level,
    }


def analyze_function_signature(signature: str) -> dict:
    """Analyze function signature structure"""
    if not signature:
        return {}
    
    # Extract function name
    func_match = re.search(r'def\s+(\w+)\s*\(', signature)
    func_name = func_match.group(1) if func_match else "unknown"
    
    # Count parameters
    params_match = re.search(r'\((.*?)\)', signature, re.DOTALL)
    params_str = params_match.group(1) if params_match else ""
    params = [p.strip() for p in params_str.split(',') if p.strip()]
    
    # Detect return type annotation
    return_type_match = re.search(r'->\s*(.+?):', signature)
    return_type = return_type_match.group(1).strip() if return_type_match else None
    
    # Check for type hints in parameters
    has_param_types = ':' in params_str
    
    return {
        "function_name": func_name,
        "param_count": len(params),
        "has_return_type": return_type is not None,
        "return_type": return_type,
        "has_param_types": has_param_types,
    }


def calculate_similarity(text1: str, text2: str) -> float:
    """Calculate text similarity ratio"""
    return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()


def analyze_overlap(datasets: dict[str, list[dict]]) -> dict:
    """Analyze overlap between datasets"""
    results = {}
    dataset_names = list(datasets.keys())
    
    for i, name1 in enumerate(dataset_names):
        for name2 in dataset_names[i+1:]:
            data1 = datasets[name1]
            data2 = datasets[name2]
            
            # ID overlap
            ids1 = set(d.get("id", "") for d in data1)
            ids2 = set(d.get("id", "") for d in data2)
            id_overlap = ids1 & ids2
            
            # Instruction overlap
            instructions1 = {d.get("id", ""): d.get("instruction", "") for d in data1}
            instructions2 = {d.get("id", ""): d.get("instruction", "") for d in data2}
            
            exact_matches = 0
            similar_matches = 0  # > 0.9 similarity
            high_similar_matches = 0  # > 0.8 similarity
            
            for id1, inst1 in instructions1.items():
                for id2, inst2 in instructions2.items():
                    if inst1 == inst2:
                        exact_matches += 1
                    else:
                        sim = calculate_similarity(inst1, inst2)
                        if sim > 0.9:
                            similar_matches += 1
                        elif sim > 0.8:
                            high_similar_matches += 1
            
            key = f"{name1}_vs_{name2}"
            results[key] = {
                "id_overlap_count": len(id_overlap),
                "id_overlap_percentage": round(len(id_overlap) / min(len(ids1), len(ids2)) * 100, 2) if min(len(ids1), len(ids2)) > 0 else 0,
                "overlapping_ids": list(id_overlap)[:10],  # First 10 for reference
                "exact_instruction_matches": exact_matches,
                "similar_instruction_matches_90": similar_matches,
                "similar_instruction_matches_80": high_similar_matches,
            }
    
    return results


def analyze_single_dataset(name: str, data: list[dict]) -> dict:
    """Perform comprehensive analysis on a single dataset"""
    print(f"  Analyzing {name}...")
    
    # Basic stats
    basic_stats = {
        "sample_count": len(data),
        "file_size_bytes": os.path.getsize(SPLIT_DATASETS[name]),
    }
    
    # Field analysis
    all_fields = set()
    for entry in data:
        all_fields.update(entry.keys())
    
    field_analysis = {
        "all_fields": list(all_fields),
        "required_fields": ["id", "instruction", "signature", "reference", "tests"],
    }
    
    # Check field completeness
    field_completeness = {}
    for field in field_analysis["required_fields"]:
        present = sum(1 for d in data if d.get(field))
        field_completeness[field] = {
            "present": present,
            "missing": len(data) - present,
            "completeness_pct": round(present / len(data) * 100, 2)
        }
    field_analysis["completeness"] = field_completeness
    
    # Category analysis
    categories = []
    for entry in data:
        if "_category" in entry and entry["_category"]:
            categories.append(entry["_category"])
        else:
            categories.append(infer_category(entry.get("instruction", "")))
    
    category_dist = Counter(categories)
    
    # Difficulty analysis
    difficulties = [entry.get("_difficulty") for entry in data if entry.get("_difficulty") is not None]
    difficulty_dist = Counter(difficulties)
    
    # Text analysis
    instructions = [d.get("instruction", "") for d in data if d.get("instruction")]
    references = [d.get("reference", "") for d in data if d.get("reference")]
    signatures = [d.get("signature", "") for d in data if d.get("signature")]
    
    text_analysis = {
        "instruction_stats": calculate_text_stats(instructions),
        "reference_stats": calculate_text_stats(references),
        "signature_stats": calculate_text_stats(signatures),
    }
    
    # Test case analysis
    test_analyses = [analyze_test_cases(d.get("tests", "")) for d in data]
    assertion_counts = [t["assertion_count"] for t in test_analyses]
    
    test_analysis = {
        "assertion_stats": {
            "min": min(assertion_counts) if assertion_counts else 0,
            "max": max(assertion_counts) if assertion_counts else 0,
            "mean": round(mean(assertion_counts), 2) if assertion_counts else 0,
            "median": round(median(assertion_counts), 2) if assertion_counts else 0,
        },
        "samples_with_edge_cases": sum(1 for t in test_analyses if t["has_edge_cases"]),
        "samples_with_error_tests": sum(1 for t in test_analyses if t["has_error_tests"]),
        "samples_with_no_assertions": sum(1 for a in assertion_counts if a == 0),
        "samples_with_single_assertion": sum(1 for a in assertion_counts if a == 1),
        "samples_with_weak_tests": sum(1 for a in assertion_counts if a <= 2),
    }
    
    # Reference code analysis
    ref_analyses = [analyze_reference_code(d.get("reference", "")) for d in data]
    
    code_analysis = {
        "avg_code_lines": round(mean([r.get("code_lines", 0) for r in ref_analyses]), 2),
        "library_usage": Counter([lib for r in ref_analyses for lib in r.get("libraries_used", [])]),
        "patterns": {
            "with_loops": sum(1 for r in ref_analyses if r.get("patterns", {}).get("has_loops")),
            "with_recursion": sum(1 for r in ref_analyses if r.get("patterns", {}).get("has_recursion")),
            "with_comprehensions": sum(1 for r in ref_analyses if r.get("patterns", {}).get("has_comprehensions")),
            "with_lambda": sum(1 for r in ref_analyses if r.get("patterns", {}).get("has_lambda")),
            "with_try_except": sum(1 for r in ref_analyses if r.get("patterns", {}).get("has_try_except")),
            "with_classes": sum(1 for r in ref_analyses if r.get("patterns", {}).get("has_class")),
            "with_type_hints": sum(1 for r in ref_analyses if r.get("patterns", {}).get("has_type_hints")),
        }
    }
    
    # Signature analysis
    sig_analyses = [analyze_function_signature(d.get("signature", "")) for d in data]
    param_counts = [s.get("param_count", 0) for s in sig_analyses]
    return_types = Counter([s.get("return_type", "None") for s in sig_analyses if s.get("return_type")])
    
    signature_analysis = {
        "param_count_stats": {
            "min": min(param_counts) if param_counts else 0,
            "max": max(param_counts) if param_counts else 0,
            "mean": round(mean(param_counts), 2) if param_counts else 0,
        },
        "with_return_type": sum(1 for s in sig_analyses if s.get("has_return_type")),
        "with_param_types": sum(1 for s in sig_analyses if s.get("has_param_types")),
        "return_type_distribution": dict(return_types.most_common(10)),
    }
    
    # ID format analysis
    ids = [d.get("id", "") for d in data]
    id_formats = Counter()
    for id_val in ids:
        if re.match(r'^problem_\d+$', id_val):
            id_formats["problem_N"] += 1
        elif re.match(r'^[a-f0-9-]{36}$', id_val):
            id_formats["uuid"] += 1
        else:
            id_formats["other"] += 1
    
    return {
        "basic_stats": basic_stats,
        "field_analysis": field_analysis,
        "category_distribution": dict(category_dist.most_common()),
        "difficulty_distribution": dict(sorted(difficulty_dist.items())),
        "text_analysis": text_analysis,
        "test_analysis": test_analysis,
        "code_analysis": code_analysis,
        "signature_analysis": signature_analysis,
        "id_format_distribution": dict(id_formats),
    }


def generate_detailed_report(analysis_results: dict, overlap_results: dict) -> str:
    """Generate comprehensive English analysis report"""
    
    report = []
    report.append("# Comprehensive Dataset Analysis Report")
    report.append(f"\n**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("**Scope:** Split Datasets (train_split, test_split, valid_split)")
    report.append("\n---\n")
    
    # Executive Summary
    report.append("## 1. Executive Summary")
    report.append("")
    
    total_samples = sum(r["basic_stats"]["sample_count"] for r in analysis_results.values())
    train_count = analysis_results["train_split"]["basic_stats"]["sample_count"]
    test_count = analysis_results["test_split"]["basic_stats"]["sample_count"]
    valid_count = analysis_results["valid_split"]["basic_stats"]["sample_count"]
    
    report.append(f"This report provides a comprehensive analysis of the final split datasets used for LLM training.")
    report.append("")
    report.append("### Key Statistics")
    report.append("")
    report.append("| Metric | Value |")
    report.append("|--------|-------|")
    report.append(f"| Total Samples | **{total_samples}** |")
    report.append(f"| Training Set | {train_count} ({train_count/total_samples*100:.1f}%) |")
    report.append(f"| Validation Set | {valid_count} ({valid_count/total_samples*100:.1f}%) |")
    report.append(f"| Test Set | {test_count} ({test_count/total_samples*100:.1f}%) |")
    report.append(f"| Split Ratio | {round(train_count/total_samples*100)}:{round(valid_count/total_samples*100)}:{round(test_count/total_samples*100)} (Train:Valid:Test) |")
    report.append("")
    
    # Data Quality Summary
    report.append("### Data Quality Summary")
    report.append("")
    
    # Check for issues
    issues = []
    for name, results in analysis_results.items():
        weak_tests = results["test_analysis"]["samples_with_weak_tests"]
        if weak_tests > 0:
            issues.append(f"- **{name}**: {weak_tests} samples with weak test coverage (≤2 assertions)")
    
    # Check overlap
    for key, overlap in overlap_results.items():
        if overlap["id_overlap_count"] > 0:
            issues.append(f"- **{key}**: {overlap['id_overlap_count']} overlapping IDs detected ({overlap['id_overlap_percentage']}%)")
    
    if issues:
        report.append("> [!WARNING]")
        report.append("> **Issues Detected:**")
        for issue in issues:
            report.append(f"> {issue}")
        report.append("")
    else:
        report.append("> [!NOTE]")
        report.append("> No critical issues detected. Dataset quality is good.")
        report.append("")
    
    report.append("---\n")
    
    # Dataset Overview
    report.append("## 2. Dataset Overview")
    report.append("")
    report.append("### 2.1 Sample Distribution")
    report.append("")
    report.append("| Dataset | Samples | File Size | Avg. Instruction Length | Avg. Reference Lines |")
    report.append("|---------|---------|-----------|------------------------|---------------------|")
    
    for name in ["train_split", "valid_split", "test_split"]:
        r = analysis_results[name]
        samples = r["basic_stats"]["sample_count"]
        size = r["basic_stats"]["file_size_bytes"] / 1024  # KB
        avg_inst = r["text_analysis"]["instruction_stats"]["char_length"]["mean"]
        avg_ref = r["text_analysis"]["reference_stats"]["line_count"]["mean"]
        report.append(f"| {name} | {samples} | {size:.1f} KB | {avg_inst:.0f} chars | {avg_ref:.1f} lines |")
    
    report.append("")
    
    # Field Structure
    report.append("### 2.2 Data Field Structure")
    report.append("")
    report.append("Each sample contains the following fields:")
    report.append("")
    report.append("| Field | Description | Completeness |")
    report.append("|-------|-------------|--------------|")
    report.append("| `id` | Unique identifier | 100% |")
    report.append("| `instruction` | Natural language problem description | 100% |")
    report.append("| `signature` | Function signature with parameters | 100% |")
    report.append("| `reference` | Reference solution code | 100% |")
    report.append("| `tests` | Test cases for validation | 100% |")
    report.append("| `_category` | Problem category (optional) | Varies |")
    report.append("| `_difficulty` | Difficulty level 1-10 (optional) | Varies |")
    report.append("")
    
    report.append("---\n")
    
    # Text Length Analysis
    report.append("## 3. Text Length Analysis")
    report.append("")
    
    report.append("### 3.1 Instruction Length Statistics")
    report.append("")
    report.append("| Dataset | Min | Max | Mean | Median | P95 | Std Dev |")
    report.append("|---------|-----|-----|------|--------|-----|---------|")
    
    for name in ["train_split", "valid_split", "test_split"]:
        stats = analysis_results[name]["text_analysis"]["instruction_stats"]["char_length"]
        report.append(f"| {name} | {stats['min']} | {stats['max']} | {stats['mean']:.0f} | {stats['median']:.0f} | {stats['p95']} | {stats['std']:.0f} |")
    
    report.append("")
    
    report.append("### 3.2 Reference Code Statistics")
    report.append("")
    report.append("| Dataset | Min Lines | Max Lines | Mean Lines | Median Lines |")
    report.append("|---------|-----------|-----------|------------|--------------|")
    
    for name in ["train_split", "valid_split", "test_split"]:
        stats = analysis_results[name]["text_analysis"]["reference_stats"]["line_count"]
        report.append(f"| {name} | {stats['min']} | {stats['max']} | {stats['mean']:.1f} | - |")
    
    report.append("")
    
    report.append("---\n")
    
    # Category Analysis
    report.append("## 4. Problem Category Analysis")
    report.append("")
    report.append("### 4.1 Category Distribution")
    report.append("")
    
    # Aggregate categories
    all_categories = Counter()
    for r in analysis_results.values():
        all_categories.update(r["category_distribution"])
    
    report.append("| Category | Total Count | Percentage |")
    report.append("|----------|-------------|------------|")
    
    for cat, count in all_categories.most_common():
        pct = count / total_samples * 100
        report.append(f"| {cat} | {count} | {pct:.1f}% |")
    
    report.append("")
    
    # Category by dataset
    report.append("### 4.2 Category Distribution by Dataset")
    report.append("")
    report.append("| Category | train_split | valid_split | test_split |")
    report.append("|----------|-------------|-------------|------------|")
    
    categories = list(all_categories.keys())
    for cat in categories:
        train_c = analysis_results["train_split"]["category_distribution"].get(cat, 0)
        valid_c = analysis_results["valid_split"]["category_distribution"].get(cat, 0)
        test_c = analysis_results["test_split"]["category_distribution"].get(cat, 0)
        report.append(f"| {cat} | {train_c} | {valid_c} | {test_c} |")
    
    report.append("")
    
    # Category balance analysis
    report.append("### 4.3 Category Balance Assessment")
    report.append("")
    
    top_category = all_categories.most_common(1)[0]
    bottom_categories = all_categories.most_common()[-3:]
    
    report.append(f"- **Dominant Category:** `{top_category[0]}` with {top_category[1]} samples ({top_category[1]/total_samples*100:.1f}%)")
    report.append(f"- **Underrepresented Categories:** {', '.join([f'`{c[0]}`' for c in bottom_categories])}")
    report.append("")
    
    if top_category[1] / total_samples > 0.3:
        report.append("> [!WARNING]")
        report.append(f"> Category imbalance detected. `{top_category[0]}` represents over 30% of the dataset.")
        report.append("> Consider augmenting underrepresented categories for better model generalization.")
        report.append("")
    
    report.append("---\n")
    
    # Difficulty Analysis
    report.append("## 5. Difficulty Level Analysis")
    report.append("")
    
    # Aggregate difficulties
    all_difficulties = Counter()
    for r in analysis_results.values():
        all_difficulties.update(r["difficulty_distribution"])
    
    if all_difficulties:
        report.append("### 5.1 Difficulty Distribution")
        report.append("")
        report.append("| Difficulty Level | Count | Percentage |")
        report.append("|------------------|-------|------------|")
        
        for level in sorted(all_difficulties.keys()):
            count = all_difficulties[level]
            pct = count / total_samples * 100
            report.append(f"| Level {level} | {count} | {pct:.1f}% |")
        
        report.append("")
        
        # Difficulty by dataset
        report.append("### 5.2 Difficulty by Dataset")
        report.append("")
        report.append("| Dataset | Avg Difficulty | Min | Max | Labeled Samples |")
        report.append("|---------|----------------|-----|-----|-----------------|")
        
        for name in ["train_split", "valid_split", "test_split"]:
            diff_dist = analysis_results[name]["difficulty_distribution"]
            if diff_dist:
                levels = [k for k in diff_dist.keys() if isinstance(k, int)]
                if levels:
                    weighted_avg = sum(k * v for k, v in diff_dist.items() if isinstance(k, int)) / sum(v for k, v in diff_dist.items() if isinstance(k, int))
                    total_labeled = sum(v for k, v in diff_dist.items() if isinstance(k, int))
                    report.append(f"| {name} | {weighted_avg:.1f} | {min(levels)} | {max(levels)} | {total_labeled} |")
                else:
                    report.append(f"| {name} | N/A | N/A | N/A | 0 |")
            else:
                report.append(f"| {name} | N/A | N/A | N/A | 0 |")
        
        report.append("")
    else:
        report.append("> [!NOTE]")
        report.append("> No difficulty labels found in the datasets.")
        report.append("")
    
    report.append("---\n")
    
    # Test Case Analysis
    report.append("## 6. Test Case Quality Analysis")
    report.append("")
    
    report.append("### 6.1 Assertion Statistics")
    report.append("")
    report.append("| Dataset | Min | Max | Mean | Median |")
    report.append("|---------|-----|-----|------|--------|")
    
    for name in ["train_split", "valid_split", "test_split"]:
        stats = analysis_results[name]["test_analysis"]["assertion_stats"]
        report.append(f"| {name} | {stats['min']} | {stats['max']} | {stats['mean']:.1f} | {stats['median']:.0f} |")
    
    report.append("")
    
    report.append("### 6.2 Test Quality Indicators")
    report.append("")
    report.append("| Dataset | No Assertions | Single Assertion | Weak Tests (≤2) | Edge Cases | Error Tests |")
    report.append("|---------|---------------|------------------|-----------------|------------|-------------|")
    
    for name in ["train_split", "valid_split", "test_split"]:
        t = analysis_results[name]["test_analysis"]
        total = analysis_results[name]["basic_stats"]["sample_count"]
        report.append(f"| {name} | {t['samples_with_no_assertions']} | {t['samples_with_single_assertion']} | {t['samples_with_weak_tests']} ({t['samples_with_weak_tests']/total*100:.1f}%) | {t['samples_with_edge_cases']} | {t['samples_with_error_tests']} |")
    
    report.append("")
    
    # Quality assessment
    total_weak = sum(r["test_analysis"]["samples_with_weak_tests"] for r in analysis_results.values())
    if total_weak > 0:
        report.append("> [!IMPORTANT]")
        report.append(f"> {total_weak} samples ({total_weak/total_samples*100:.1f}%) have weak test coverage (≤2 assertions).")
        report.append("> Recommended: Augment test cases for these samples to ensure robust evaluation.")
        report.append("")
    
    report.append("---\n")
    
    # Code Analysis
    report.append("## 7. Reference Code Analysis")
    report.append("")
    
    report.append("### 7.1 Code Complexity")
    report.append("")
    report.append("| Dataset | Avg Code Lines | With Loops | With Recursion | With Comprehensions |")
    report.append("|---------|----------------|------------|----------------|---------------------|")
    
    for name in ["train_split", "valid_split", "test_split"]:
        c = analysis_results[name]["code_analysis"]
        total = analysis_results[name]["basic_stats"]["sample_count"]
        report.append(f"| {name} | {c['avg_code_lines']:.1f} | {c['patterns']['with_loops']} ({c['patterns']['with_loops']/total*100:.0f}%) | {c['patterns']['with_recursion']} | {c['patterns']['with_comprehensions']} |")
    
    report.append("")
    
    report.append("### 7.2 Library Usage")
    report.append("")
    
    # Aggregate library usage
    all_libs = Counter()
    for r in analysis_results.values():
        all_libs.update(r["code_analysis"]["library_usage"])
    
    report.append("| Library | Usage Count | Percentage of Samples |")
    report.append("|---------|-------------|----------------------|")
    
    for lib, count in all_libs.most_common(10):
        pct = count / total_samples * 100
        report.append(f"| `{lib}` | {count} | {pct:.1f}% |")
    
    report.append("")
    
    report.append("### 7.3 Code Pattern Distribution")
    report.append("")
    report.append("| Pattern | train_split | valid_split | test_split | Total |")
    report.append("|---------|-------------|-------------|------------|-------|")
    
    patterns = ["with_loops", "with_recursion", "with_comprehensions", "with_lambda", "with_try_except", "with_classes", "with_type_hints"]
    for pattern in patterns:
        train_v = analysis_results["train_split"]["code_analysis"]["patterns"][pattern]
        valid_v = analysis_results["valid_split"]["code_analysis"]["patterns"][pattern]
        test_v = analysis_results["test_split"]["code_analysis"]["patterns"][pattern]
        total_v = train_v + valid_v + test_v
        pattern_name = pattern.replace("with_", "").replace("_", " ").title()
        report.append(f"| {pattern_name} | {train_v} | {valid_v} | {test_v} | {total_v} |")
    
    report.append("")
    
    report.append("---\n")
    
    # Function Signature Analysis
    report.append("## 8. Function Signature Analysis")
    report.append("")
    
    report.append("### 8.1 Parameter Statistics")
    report.append("")
    report.append("| Dataset | Min Params | Max Params | Avg Params | With Return Type | With Param Types |")
    report.append("|---------|------------|------------|------------|------------------|------------------|")
    
    for name in ["train_split", "valid_split", "test_split"]:
        s = analysis_results[name]["signature_analysis"]
        total = analysis_results[name]["basic_stats"]["sample_count"]
        report.append(f"| {name} | {s['param_count_stats']['min']} | {s['param_count_stats']['max']} | {s['param_count_stats']['mean']:.1f} | {s['with_return_type']} ({s['with_return_type']/total*100:.0f}%) | {s['with_param_types']} ({s['with_param_types']/total*100:.0f}%) |")
    
    report.append("")
    
    report.append("### 8.2 Return Type Distribution")
    report.append("")
    
    # Aggregate return types
    all_return_types = Counter()
    for r in analysis_results.values():
        all_return_types.update(r["signature_analysis"]["return_type_distribution"])
    
    report.append("| Return Type | Count | Percentage |")
    report.append("|-------------|-------|------------|")
    
    for rt, count in all_return_types.most_common(10):
        pct = count / total_samples * 100
        report.append(f"| `{rt}` | {count} | {pct:.1f}% |")
    
    report.append("")
    
    report.append("---\n")
    
    # Overlap Analysis
    report.append("## 9. Dataset Overlap Analysis")
    report.append("")
    report.append("### 9.1 ID Overlap Check")
    report.append("")
    report.append("| Comparison | ID Overlap | Overlap % | Exact Matches | Similar (>90%) |")
    report.append("|------------|------------|-----------|---------------|----------------|")
    
    for key, overlap in overlap_results.items():
        report.append(f"| {key.replace('_vs_', ' vs ')} | {overlap['id_overlap_count']} | {overlap['id_overlap_percentage']:.1f}% | {overlap['exact_instruction_matches']} | {overlap['similar_instruction_matches_90']} |")
    
    report.append("")
    
    # Overlap assessment
    has_overlap = any(o["id_overlap_count"] > 0 for o in overlap_results.values())
    
    if has_overlap:
        report.append("> [!CAUTION]")
        report.append("> **Data Leakage Detected!**")
        report.append("> Overlapping samples between training and evaluation sets can lead to:")
        report.append("> - Overly optimistic performance metrics")
        report.append("> - Poor generalization to unseen data")
        report.append("> - Invalid model evaluation")
        report.append(">")
        report.append("> **Recommendation:** Remove overlapping samples or regenerate the splits.")
        report.append("")
    else:
        report.append("> [!NOTE]")
        report.append("> ✅ No overlap detected between datasets. Data splits are clean and independent.")
        report.append("")
    
    report.append("---\n")
    
    # Data Quality Assessment
    report.append("## 10. Data Quality Assessment")
    report.append("")
    
    report.append("### 10.1 Quality Checklist")
    report.append("")
    
    # Check various quality metrics
    checks = []
    
    # Field completeness
    all_complete = all(
        r["field_analysis"]["completeness"][f]["completeness_pct"] == 100 
        for r in analysis_results.values() 
        for f in ["id", "instruction", "signature", "reference", "tests"]
    )
    checks.append(("Required fields complete", all_complete))
    
    # No overlap
    no_overlap = not has_overlap
    checks.append(("No data leakage between splits", no_overlap))
    
    # Balanced split ratio
    train_ratio = train_count / total_samples
    valid_ratio = valid_count / total_samples
    test_ratio = test_count / total_samples
    balanced = 0.7 <= train_ratio <= 0.85 and 0.075 <= valid_ratio <= 0.15 and 0.075 <= test_ratio <= 0.15
    checks.append(("Appropriate split ratios", balanced))
    
    # Good test coverage
    good_tests = all(r["test_analysis"]["samples_with_weak_tests"] / r["basic_stats"]["sample_count"] < 0.1 for r in analysis_results.values())
    checks.append(("Strong test coverage (>90%)", good_tests))
    
    # Category diversity
    category_count = len(all_categories)
    diverse_categories = category_count >= 5
    checks.append(("Diverse problem categories (≥5)", diverse_categories))
    
    report.append("| Check | Status |")
    report.append("|-------|--------|")
    
    for check_name, passed in checks:
        status = "✅ Pass" if passed else "❌ Fail"
        report.append(f"| {check_name} | {status} |")
    
    report.append("")
    
    # Overall score
    passed_count = sum(1 for _, p in checks if p)
    total_checks = len(checks)
    score = passed_count / total_checks * 100
    
    report.append(f"### 10.2 Overall Quality Score: **{score:.0f}/100**")
    report.append("")
    
    if score >= 80:
        report.append("> [!TIP]")
        report.append("> Dataset quality is **GOOD**. Ready for training with minor improvements.")
    elif score >= 60:
        report.append("> [!WARNING]")
        report.append("> Dataset quality is **ACCEPTABLE** but has issues that should be addressed.")
    else:
        report.append("> [!CAUTION]")
        report.append("> Dataset quality is **POOR**. Critical issues must be resolved before training.")
    
    report.append("")
    
    report.append("---\n")
    
    # Recommendations
    report.append("## 11. Recommendations")
    report.append("")
    
    recommendations = []
    
    if has_overlap:
        recommendations.append({
            "priority": "🔴 Critical",
            "issue": "Data leakage between splits",
            "recommendation": "Remove overlapping samples or regenerate splits with proper stratification"
        })
    
    if total_weak > 0:
        recommendations.append({
            "priority": "🟡 Medium",
            "issue": f"{total_weak} samples with weak test coverage",
            "recommendation": "Augment test cases to ensure at least 3 assertions per sample"
        })
    
    if top_category[1] / total_samples > 0.3:
        recommendations.append({
            "priority": "🟡 Medium",
            "issue": f"Category imbalance ({top_category[0]} dominates)",
            "recommendation": "Add more samples from underrepresented categories or apply weighted sampling"
        })
    
    if not all_difficulties:
        recommendations.append({
            "priority": "🟢 Low",
            "issue": "Missing difficulty labels",
            "recommendation": "Add difficulty labels to enable stratified analysis and curriculum learning"
        })
    
    if recommendations:
        report.append("| Priority | Issue | Recommendation |")
        report.append("|----------|-------|----------------|")
        for rec in recommendations:
            report.append(f"| {rec['priority']} | {rec['issue']} | {rec['recommendation']} |")
        report.append("")
    else:
        report.append("> No critical recommendations. Dataset is ready for use.")
        report.append("")
    
    report.append("---\n")
    
    # Sample Examples
    report.append("## 12. Sample Examples")
    report.append("")
    
    # Load one sample from each dataset for display
    for name in ["train_split", "valid_split", "test_split"]:
        data = load_jsonl(SPLIT_DATASETS[name])
        if data:
            sample = data[0]
            report.append(f"### Example from {name}")
            report.append("")
            report.append(f"**ID:** `{sample.get('id', 'N/A')}`")
            report.append("")
            report.append("**Instruction:**")
            report.append("```")
            report.append(sample.get("instruction", "N/A")[:500] + ("..." if len(sample.get("instruction", "")) > 500 else ""))
            report.append("```")
            report.append("")
            report.append("**Signature:**")
            report.append("```python")
            report.append(sample.get("signature", "N/A"))
            report.append("```")
            report.append("")
    
    report.append("---\n")
    
    # Appendix
    report.append("## Appendix: Detailed Statistics")
    report.append("")
    report.append("For detailed JSON data, see: `dataset_analysis_split_data.json`")
    report.append("")
    
    return "\n".join(report)


def main():
    print("=" * 60)
    print("Split Dataset Analysis for LLM Training Pipeline")
    print("=" * 60)
    print()
    
    # Load datasets
    print("Loading datasets...")
    datasets = {}
    for name, path in SPLIT_DATASETS.items():
        print(f"  Loading {name}...")
        datasets[name] = load_jsonl(path)
        print(f"    Loaded {len(datasets[name])} samples")
    
    print()
    
    # Analyze each dataset
    print("Analyzing datasets...")
    analysis_results = {}
    for name in datasets:
        analysis_results[name] = analyze_single_dataset(name, datasets[name])
    
    print()
    
    # Analyze overlap
    print("Checking for overlap...")
    overlap_results = analyze_overlap(datasets)
    
    print()
    
    # Generate report
    print("Generating report...")
    report = generate_detailed_report(analysis_results, overlap_results)
    
    # Save report
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    report_path = os.path.join(OUTPUT_DIR, "split_dataset_analysis_report.md")
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"  Report saved to: {report_path}")
    
    # Save JSON data
    json_path = os.path.join(OUTPUT_DIR, "split_dataset_analysis_data.json")
    json_data = {
        "analysis_results": analysis_results,
        "overlap_results": overlap_results,
        "generated_at": datetime.now().isoformat(),
    }
    
    # Convert Counter objects to dicts for JSON serialization
    def convert_counters(obj):
        if isinstance(obj, Counter):
            return dict(obj)
        elif isinstance(obj, dict):
            return {k: convert_counters(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_counters(item) for item in obj]
        return obj
    
    json_data = convert_counters(json_data)
    
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False)
    print(f"  JSON data saved to: {json_path}")
    
    print()
    print("=" * 60)
    print("Analysis complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
