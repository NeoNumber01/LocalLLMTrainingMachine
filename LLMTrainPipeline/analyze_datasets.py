#!/usr/bin/env python3
"""
Comprehensive Dataset Analysis Script for LLM Training Data
Analyzes: train_final, train_split, test_split, valid_split datasets
"""

import json
import os
import re
from collections import Counter, defaultdict
from typing import Any
import difflib

# Dataset paths
BASE_DIR = r"c:\Users\Shu Leo\Desktop\practical course\LLMTrainPipeline\backend\storage\final refined version"
DATASETS = {
    "train_final": os.path.join(BASE_DIR, "train_final.jsonl"),
    "train_split": os.path.join(BASE_DIR, "train_split.jsonl"),
    "test_split": os.path.join(BASE_DIR, "test_split.jsonl"),
    "valid_split": os.path.join(BASE_DIR, "valid_split.jsonl"),
}

def load_jsonl(path: str) -> list[dict]:
    """Load JSONL file into list of dictionaries."""
    entries = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries

def get_text_length_stats(texts: list[str]) -> dict:
    """Calculate length statistics for a list of texts."""
    lengths = [len(t) for t in texts]
    if not lengths:
        return {}
    lengths.sort()
    n = len(lengths)
    return {
        "count": n,
        "min": min(lengths),
        "max": max(lengths),
        "mean": sum(lengths) / n,
        "median": lengths[n // 2],
        "p95": lengths[int(n * 0.95)] if n > 1 else lengths[0],
    }

def extract_categories_from_instruction(instruction: str) -> list[str]:
    """Infer problem categories from instruction text."""
    categories = []
    instruction_lower = instruction.lower()
    
    # Category keywords mapping
    category_keywords = {
        "string": ["string", "character", "substring", "text", "letter", "word", "regex", "pattern"],
        "list/array": ["list", "array", "element", "sequence", "nested"],
        "math": ["number", "digit", "prime", "factorial", "power", "arithmetic", "sum", "product", "multiply", "divide", "sqrt", "fibonacci", "gcd", "lcm"],
        "sorting": ["sort", "order", "ascending", "descending", "arrange"],
        "searching": ["search", "find", "locate", "index", "first occurrence", "last occurrence"],
        "dictionary": ["dictionary", "dict", "map", "key", "value", "hash"],
        "tuple": ["tuple", "pair"],
        "set": ["set", "unique", "distinct", "duplicate"],
        "recursion": ["recursive", "recursion"],
        "dp": ["dynamic programming", "memoization", "minimum cost", "maximum sum", "optimal"],
        "tree/graph": ["tree", "graph", "node", "binary", "traverse", "path", "visited"],
        "bit manipulation": ["bit", "binary", "xor", "and", "or", "shift", "parity"],
        "geometry": ["area", "perimeter", "circle", "triangle", "square", "rectangle", "polygon", "volume", "surface"],
        "matrix": ["matrix", "2d array", "row", "column", "transpose"],
        "heap": ["heap", "priority queue", "heapify"],
        "stack/queue": ["stack", "queue", "push", "pop", "lifo", "fifo"],
        "linked list": ["linked list", "node", "pointer"],
        "date/time": ["date", "time", "calendar", "month", "year", "day"],
        "file/io": ["file", "read", "write", "input", "output"],
        "combinatorics": ["combination", "permutation", "binomial", "factorial", "choose"],
        "validation": ["check", "validate", "verify", "is valid", "match"],
    }
    
    for category, keywords in category_keywords.items():
        for kw in keywords:
            if kw in instruction_lower:
                categories.append(category)
                break
    
    if not categories:
        categories.append("other")
    
    return list(set(categories))

def calculate_similarity(text1: str, text2: str) -> float:
    """Calculate similarity ratio between two texts."""
    return difflib.SequenceMatcher(None, text1.lower(), text2.lower()).ratio()

def analyze_overlap(datasets: dict[str, list[dict]]) -> dict:
    """Analyze overlap between datasets based on instruction similarity."""
    overlap_results = {}
    dataset_names = list(datasets.keys())
    
    for i, name1 in enumerate(dataset_names):
        for name2 in dataset_names[i+1:]:
            exact_matches = 0
            similar_matches = 0  # > 0.9 similarity
            id_overlaps = 0
            
            ids1 = {e['id'] for e in datasets[name1]}
            ids2 = {e['id'] for e in datasets[name2]}
            id_overlaps = len(ids1 & ids2)
            
            instructions1 = {e['id']: e['instruction'] for e in datasets[name1]}
            instructions2 = {e['id']: e['instruction'] for e in datasets[name2]}
            
            # Check for exact instruction matches
            inst_set1 = set(instructions1.values())
            inst_set2 = set(instructions2.values())
            exact_matches = len(inst_set1 & inst_set2)
            
            # Sample-based similarity check (for performance)
            sample_size = min(100, len(instructions1), len(instructions2))
            sampled_insts1 = list(instructions1.values())[:sample_size]
            
            for inst1 in sampled_insts1:
                for inst2 in instructions2.values():
                    if inst1 != inst2 and calculate_similarity(inst1, inst2) > 0.9:
                        similar_matches += 1
                        break
            
            overlap_results[f"{name1}_vs_{name2}"] = {
                "id_overlaps": id_overlaps,
                "id_overlap_pct_1": id_overlaps / len(ids1) * 100 if ids1 else 0,
                "id_overlap_pct_2": id_overlaps / len(ids2) * 100 if ids2 else 0,
                "exact_instruction_matches": exact_matches,
                "similar_instruction_matches": similar_matches,
            }
    
    return overlap_results

def analyze_dataset(data: list[dict], name: str) -> dict:
    """Analyze a single dataset comprehensively."""
    result = {
        "name": name,
        "total_samples": len(data),
        "fields": set(),
        "missing_fields": defaultdict(int),
        "categories": Counter(),
        "difficulty_distribution": Counter(),
        "instruction_lengths": [],
        "reference_lengths": [],
        "test_counts": [],
        "signature_types": Counter(),
        "empty_values": defaultdict(int),
        "ids": set(),
    }
    
    for entry in data:
        # Collect all fields
        result["fields"].update(entry.keys())
        result["ids"].add(entry.get("id", ""))
        
        # Check for missing/empty fields
        for field in ["id", "instruction", "signature", "reference", "tests"]:
            if field not in entry:
                result["missing_fields"][field] += 1
            elif not entry[field] or (isinstance(entry[field], str) and not entry[field].strip()):
                result["empty_values"][field] += 1
        
        # Instruction analysis
        instruction = entry.get("instruction", "")
        result["instruction_lengths"].append(len(instruction))
        
        # Categories (explicit or inferred)
        if "_category" in entry:
            result["categories"][entry["_category"]] += 1
        else:
            for cat in extract_categories_from_instruction(instruction):
                result["categories"][cat] += 1
        
        # Difficulty
        if "_difficulty" in entry:
            result["difficulty_distribution"][entry["_difficulty"]] += 1
        
        # Reference (solution) analysis
        reference = entry.get("reference", "")
        result["reference_lengths"].append(len(reference))
        
        # Test count analysis
        tests = entry.get("tests", "")
        test_count = tests.count("assert ")
        result["test_counts"].append(test_count)
        
        # Signature analysis (return type)
        signature = entry.get("signature", "")
        if "-> " in signature:
            return_type = signature.split("-> ")[-1].strip().rstrip(":")
            result["signature_types"][return_type] += 1
        else:
            result["signature_types"]["unspecified"] += 1
    
    # Convert sets to counts
    result["fields"] = list(result["fields"])
    result["unique_ids"] = len(result["ids"])
    result["duplicate_ids"] = len(data) - len(result["ids"])
    del result["ids"]
    
    # Calculate stats
    result["instruction_length_stats"] = get_text_length_stats(
        [str(l) for l in result["instruction_lengths"]]
    )
    result["instruction_length_stats"] = get_text_length_stats(
        [entry.get("instruction", "") for entry in data]
    )
    result["reference_length_stats"] = get_text_length_stats(
        [entry.get("reference", "") for entry in data]
    )
    result["test_count_stats"] = {
        "mean": sum(result["test_counts"]) / len(result["test_counts"]) if result["test_counts"] else 0,
        "min": min(result["test_counts"]) if result["test_counts"] else 0,
        "max": max(result["test_counts"]) if result["test_counts"] else 0,
    }
    
    # Cleanup for serialization
    result["categories"] = dict(result["categories"].most_common(20))
    result["difficulty_distribution"] = dict(result["difficulty_distribution"])
    result["signature_types"] = dict(result["signature_types"].most_common(10))
    result["missing_fields"] = dict(result["missing_fields"])
    result["empty_values"] = dict(result["empty_values"])
    del result["instruction_lengths"]
    del result["reference_lengths"]
    del result["test_counts"]
    
    return result

def check_data_quality(data: list[dict]) -> dict:
    """Check various data quality issues."""
    issues = {
        "missing_instruction": 0,
        "missing_signature": 0,
        "missing_reference": 0,
        "missing_tests": 0,
        "empty_instruction": 0,
        "very_short_instruction": 0,  # < 20 chars
        "very_long_instruction": 0,   # > 500 chars
        "empty_reference": 0,
        "very_short_reference": 0,    # < 20 chars
        "no_assertions": 0,
        "single_assertion": 0,
        "signature_mismatch": 0,      # function name in signature doesn't match reference
        "syntax_issues_reference": 0,
        "inconsistent_id_format": 0,
    }
    
    id_pattern = re.compile(r"train_final_\d{5}")
    
    for entry in data:
        # ID format check
        if not id_pattern.match(entry.get("id", "")):
            issues["inconsistent_id_format"] += 1
        
        instruction = entry.get("instruction", "")
        if not instruction:
            issues["missing_instruction"] += 1
        elif len(instruction.strip()) == 0:
            issues["empty_instruction"] += 1
        elif len(instruction) < 20:
            issues["very_short_instruction"] += 1
        elif len(instruction) > 500:
            issues["very_long_instruction"] += 1
        
        signature = entry.get("signature", "")
        if not signature:
            issues["missing_signature"] += 1
        
        reference = entry.get("reference", "")
        if not reference:
            issues["missing_reference"] += 1
        elif len(reference.strip()) == 0:
            issues["empty_reference"] += 1
        elif len(reference) < 20:
            issues["very_short_reference"] += 1
        
        tests = entry.get("tests", "")
        if not tests:
            issues["missing_tests"] += 1
        else:
            assertion_count = tests.count("assert ")
            if assertion_count == 0:
                issues["no_assertions"] += 1
            elif assertion_count == 1:
                issues["single_assertion"] += 1
        
        # Check signature-reference consistency
        if signature and reference:
            try:
                func_name_sig = signature.split("(")[0].replace("def ", "").strip()
                if func_name_sig not in reference:
                    issues["signature_mismatch"] += 1
            except:
                pass
    
    return issues

def generate_report(datasets: dict[str, list[dict]]) -> str:
    """Generate comprehensive analysis report in English."""
    report = []
    report.append("=" * 80)
    report.append("COMPREHENSIVE DATASET ANALYSIS REPORT")
    report.append("LLM Training Pipeline - Final Refined Datasets")
    report.append("=" * 80)
    report.append("")
    
    # 1. Overview Section
    report.append("## 1. DATASET OVERVIEW")
    report.append("-" * 40)
    total_samples = sum(len(d) for d in datasets.values())
    report.append(f"Total Datasets: {len(datasets)}")
    report.append(f"Total Samples: {total_samples}")
    report.append("")
    
    for name, data in datasets.items():
        report.append(f"  - {name}: {len(data)} samples")
    report.append("")
    
    # 2. Detailed Analysis per Dataset
    report.append("## 2. DETAILED DATASET ANALYSIS")
    report.append("-" * 40)
    
    analyses = {}
    for name, data in datasets.items():
        analysis = analyze_dataset(data, name)
        analyses[name] = analysis
        
        report.append(f"\n### 2.{list(datasets.keys()).index(name)+1} {name.upper()}")
        report.append(f"  Total Samples: {analysis['total_samples']}")
        report.append(f"  Unique IDs: {analysis['unique_ids']}")
        report.append(f"  Duplicate IDs: {analysis['duplicate_ids']}")
        report.append(f"  Fields: {', '.join(analysis['fields'])}")
        report.append("")
        
        report.append("  Instruction Length Statistics:")
        stats = analysis['instruction_length_stats']
        if stats:
            report.append(f"    - Min: {stats['min']} chars")
            report.append(f"    - Max: {stats['max']} chars")
            report.append(f"    - Mean: {stats['mean']:.1f} chars")
            report.append(f"    - Median: {stats['median']} chars")
            report.append(f"    - P95: {stats['p95']} chars")
        
        report.append("")
        report.append("  Reference (Solution) Length Statistics:")
        stats = analysis['reference_length_stats']
        if stats:
            report.append(f"    - Min: {stats['min']} chars")
            report.append(f"    - Max: {stats['max']} chars")
            report.append(f"    - Mean: {stats['mean']:.1f} chars")
            report.append(f"    - Median: {stats['median']} chars")
        
        report.append("")
        report.append("  Test Statistics:")
        stats = analysis['test_count_stats']
        report.append(f"    - Mean assertions per sample: {stats['mean']:.2f}")
        report.append(f"    - Min assertions: {stats['min']}")
        report.append(f"    - Max assertions: {stats['max']}")
        
        if analysis['difficulty_distribution']:
            report.append("")
            report.append("  Difficulty Distribution:")
            for diff, count in sorted(analysis['difficulty_distribution'].items()):
                report.append(f"    - Difficulty {diff}: {count} samples")
    
    # 3. Data Quality Analysis
    report.append("\n\n## 3. DATA QUALITY ANALYSIS")
    report.append("-" * 40)
    
    for name, data in datasets.items():
        quality = check_data_quality(data)
        report.append(f"\n### {name}")
        
        total = len(data)
        quality_score = 100
        issues_found = []
        
        if quality["missing_instruction"] > 0:
            pct = quality["missing_instruction"] / total * 100
            issues_found.append(f"Missing instructions: {quality['missing_instruction']} ({pct:.2f}%)")
            quality_score -= pct
        
        if quality["missing_reference"] > 0:
            pct = quality["missing_reference"] / total * 100
            issues_found.append(f"Missing references: {quality['missing_reference']} ({pct:.2f}%)")
            quality_score -= pct
        
        if quality["missing_tests"] > 0:
            pct = quality["missing_tests"] / total * 100
            issues_found.append(f"Missing tests: {quality['missing_tests']} ({pct:.2f}%)")
            quality_score -= pct
        
        if quality["no_assertions"] > 0:
            pct = quality["no_assertions"] / total * 100
            issues_found.append(f"No assertions in tests: {quality['no_assertions']} ({pct:.2f}%)")
            quality_score -= pct * 0.5
        
        if quality["single_assertion"] > 0:
            pct = quality["single_assertion"] / total * 100
            issues_found.append(f"Single assertion (weak tests): {quality['single_assertion']} ({pct:.2f}%)")
        
        if quality["very_short_instruction"] > 0:
            issues_found.append(f"Very short instructions (<20 chars): {quality['very_short_instruction']}")
        
        if quality["very_long_instruction"] > 0:
            issues_found.append(f"Very long instructions (>500 chars): {quality['very_long_instruction']}")
        
        if quality["signature_mismatch"] > 0:
            pct = quality["signature_mismatch"] / total * 100
            issues_found.append(f"Signature-reference mismatch: {quality['signature_mismatch']} ({pct:.2f}%)")
        
        if quality["inconsistent_id_format"] > 0:
            issues_found.append(f"Inconsistent ID format: {quality['inconsistent_id_format']}")
        
        quality_score = max(0, quality_score)
        report.append(f"  Quality Score: {quality_score:.1f}/100")
        
        if issues_found:
            report.append("  Issues Found:")
            for issue in issues_found:
                report.append(f"    - {issue}")
        else:
            report.append("  No significant issues found!")
    
    # 4. Overlap Analysis
    report.append("\n\n## 4. DATASET OVERLAP ANALYSIS")
    report.append("-" * 40)
    
    overlap = analyze_overlap(datasets)
    for pair, stats in overlap.items():
        report.append(f"\n### {pair.replace('_vs_', ' vs ')}")
        report.append(f"  ID Overlaps: {stats['id_overlaps']}")
        report.append(f"    - As % of first dataset: {stats['id_overlap_pct_1']:.2f}%")
        report.append(f"    - As % of second dataset: {stats['id_overlap_pct_2']:.2f}%")
        report.append(f"  Exact Instruction Matches: {stats['exact_instruction_matches']}")
        report.append(f"  Similar Instruction Matches (>90%): {stats['similar_instruction_matches']}")
    
    # 5. Problem Type Coverage
    report.append("\n\n## 5. PROBLEM TYPE COVERAGE")
    report.append("-" * 40)
    
    all_categories = Counter()
    for name, analysis in analyses.items():
        for cat, count in analysis['categories'].items():
            all_categories[cat] += count
    
    report.append("\nOverall Problem Categories Distribution:")
    for cat, count in all_categories.most_common(25):
        pct = count / total_samples * 100
        bar = "█" * int(pct / 2)
        report.append(f"  {cat:20s}: {count:5d} ({pct:5.2f}%) {bar}")
    
    # Per-dataset category breakdown
    report.append("\nPer-Dataset Category Distribution:")
    for name, analysis in analyses.items():
        report.append(f"\n  {name}:")
        for cat, count in list(analysis['categories'].items())[:10]:
            pct = count / analysis['total_samples'] * 100
            report.append(f"    - {cat}: {count} ({pct:.1f}%)")
    
    # 6. Return Type Distribution
    report.append("\n\n## 6. FUNCTION SIGNATURE ANALYSIS")
    report.append("-" * 40)
    
    for name, analysis in analyses.items():
        report.append(f"\n### {name} - Return Types:")
        for rtype, count in list(analysis['signature_types'].items())[:10]:
            pct = count / analysis['total_samples'] * 100
            report.append(f"  {rtype:20s}: {count:5d} ({pct:5.2f}%)")
    
    # 7. Summary and Recommendations
    report.append("\n\n## 7. SUMMARY AND RECOMMENDATIONS")
    report.append("-" * 40)
    
    report.append("\n### Key Findings:")
    
    # Check train/test/valid split ratio
    train_size = len(datasets.get("train_split", []))
    test_size = len(datasets.get("test_split", []))
    valid_size = len(datasets.get("valid_split", []))
    total_split = train_size + test_size + valid_size
    
    if total_split > 0:
        report.append(f"\n1. Dataset Split Ratio:")
        report.append(f"   - Training: {train_size} ({train_size/total_split*100:.1f}%)")
        report.append(f"   - Testing: {test_size} ({test_size/total_split*100:.1f}%)")
        report.append(f"   - Validation: {valid_size} ({valid_size/total_split*100:.1f}%)")
        
        # Typical split check
        if 0.7 <= train_size/total_split <= 0.85:
            report.append("   ✓ Training split is within typical range (70-85%)")
        else:
            report.append("   ⚠ Training split may be outside typical range")
    
    # Check overlap
    test_train_overlap = overlap.get("train_split_vs_test_split", {}).get("id_overlaps", 0)
    valid_train_overlap = overlap.get("train_split_vs_valid_split", {}).get("id_overlaps", 0)
    test_valid_overlap = overlap.get("test_split_vs_valid_split", {}).get("id_overlaps", 0)
    
    report.append(f"\n2. Data Leakage Check:")
    if test_train_overlap == 0 and valid_train_overlap == 0:
        report.append("   ✓ No overlap between training and test/validation sets")
    else:
        report.append(f"   ⚠ WARNING: Found overlap between train and test/valid!")
        report.append(f"      Train-Test overlap: {test_train_overlap}")
        report.append(f"      Train-Valid overlap: {valid_train_overlap}")
    
    if test_valid_overlap == 0:
        report.append("   ✓ No overlap between test and validation sets")
    else:
        report.append(f"   ⚠ Test-Validation overlap: {test_valid_overlap}")
    
    report.append(f"\n3. Category Coverage:")
    report.append(f"   - Total unique categories: {len(all_categories)}")
    top_3 = all_categories.most_common(3)
    report.append(f"   - Most common: {', '.join([f'{c[0]} ({c[1]})' for c in top_3])}")
    bottom_3 = all_categories.most_common()[-3:]
    report.append(f"   - Least common: {', '.join([f'{c[0]} ({c[1]})' for c in bottom_3])}")
    
    report.append("\n### Recommendations:")
    recommendations = []
    
    # Check for category imbalance
    if all_categories:
        max_cat_count = max(all_categories.values())
        min_cat_count = min(all_categories.values())
        if max_cat_count / min_cat_count > 10:
            recommendations.append("Consider balancing problem categories - significant imbalance detected")
    
    # Check test quality
    for name, data in datasets.items():
        quality = check_data_quality(data)
        if quality["single_assertion"] > len(data) * 0.3:
            recommendations.append(f"Consider adding more assertions to {name} - many samples have only 1 test case")
    
    # Check overlap
    if any(overlap[k]["id_overlaps"] > 0 for k in overlap if "train" in k and ("test" in k or "valid" in k)):
        recommendations.append("CRITICAL: Remove overlapping samples between train and test/valid sets to prevent data leakage")
    
    if not recommendations:
        recommendations.append("Dataset quality is good overall. No critical issues found.")
    
    for i, rec in enumerate(recommendations, 1):
        report.append(f"   {i}. {rec}")
    
    report.append("\n" + "=" * 80)
    report.append("END OF REPORT")
    report.append("=" * 80)
    
    return "\n".join(report)

def main():
    print("Loading datasets...")
    datasets = {}
    for name, path in DATASETS.items():
        if os.path.exists(path):
            datasets[name] = load_jsonl(path)
            print(f"  Loaded {name}: {len(datasets[name])} samples")
        else:
            print(f"  WARNING: {path} not found")
    
    print("\nAnalyzing datasets...")
    report = generate_report(datasets)
    
    # Save report
    output_path = os.path.join(BASE_DIR, "..", "..", "docs", "dataset_analysis_report_en.md")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"\nReport saved to: {output_path}")
    print("\n" + "=" * 80)
    print(report)
    
    # Also save as JSON for programmatic access
    json_output = os.path.join(BASE_DIR, "..", "..", "docs", "dataset_analysis_data.json")
    
    analysis_data = {
        "datasets": {},
        "overlap": analyze_overlap(datasets),
        "quality": {}
    }
    
    for name, data in datasets.items():
        analysis_data["datasets"][name] = analyze_dataset(data, name)
        analysis_data["quality"][name] = check_data_quality(data)
    
    with open(json_output, 'w', encoding='utf-8') as f:
        json.dump(analysis_data, f, indent=2, ensure_ascii=False)
    
    print(f"\nJSON data saved to: {json_output}")

if __name__ == "__main__":
    main()
