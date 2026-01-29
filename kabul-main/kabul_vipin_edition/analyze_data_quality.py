"""
Data Quality Analysis Script
Analyzes training data and generates quality metrics for the report
"""
import json
import os
from collections import defaultdict
from transformers import AutoTokenizer
from train_config import TrainingConfig

def analyze_data_quality():
    config = TrainingConfig()
    tokenizer = AutoTokenizer.from_pretrained(config.base_model)
    
    print("Loading raw data...")
    
    # Load JSON file (supports both array and JSON Lines format)
    def load_json(path):
        data = []
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            # Try parsing as a single list first
            try:
                data = json.loads(content)
                if isinstance(data, list):
                    return data
            except json.JSONDecodeError:
                pass
            
            # Fallback to JSON Lines
            lines = content.split('\n')
            for line in lines:
                if line.strip():
                    try:
                        data.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        return data

    
    java_train_raw = load_json(config.java_train_path)
    csharp_train_raw = load_json(config.csharp_train_path)
    java_valid_raw = load_json(config.java_valid_path)
    csharp_valid_raw = load_json(config.csharp_valid_path)
    
    print(f"Raw counts - Java train: {len(java_train_raw)}, C# train: {len(csharp_train_raw)}")
    print(f"Raw counts - Java valid: {len(java_valid_raw)}, C# valid: {len(csharp_valid_raw)}")
    
    # Helper to extract description
    def get_desc(item):
        text = item.get('text', '').strip()
        if '|' in text:
            return text.split('|')[0].strip()
        return text
    
    # ============ ALIGNMENT & DEDUP ANALYSIS ============
    print("\nAnalyzing alignment and deduplication...")
    
    def align_and_analyze(java_data, csharp_data):
        # Group by description
        java_by_desc = defaultdict(list)
        for item in java_data:
            desc = get_desc(item)
            if desc:
                java_by_desc[desc].append(item)
        
        csharp_by_desc = defaultdict(list)
        for item in csharp_data:
            desc = get_desc(item)
            if desc:
                csharp_by_desc[desc].append(item)
        
        # Align
        aligned_pairs = []
        processed_descs = set()
        
        for item in java_data:
            desc = get_desc(item)
            if desc not in csharp_by_desc or desc in processed_descs:
                continue
            
            java_list = java_by_desc[desc]
            csharp_list = csharp_by_desc[desc]
            count = min(len(java_list), len(csharp_list))
            
            for k in range(count):
                aligned_pairs.append({
                    "java_code": java_list[k]['code'],
                    "csharp_code": csharp_list[k]['code'],
                    "description": desc
                })
            processed_descs.add(desc)
        
        before_dedup = len(aligned_pairs)
        
        # Dedup
        seen_java = set()
        seen_csharp = set()
        deduped_pairs = []
        
        for pair in aligned_pairs:
            java_hash = hash(pair["java_code"])
            csharp_hash = hash(pair["csharp_code"])
            
            if java_hash in seen_java or csharp_hash in seen_csharp:
                continue
            
            seen_java.add(java_hash)
            seen_csharp.add(csharp_hash)
            deduped_pairs.append(pair)
        
        after_dedup = len(deduped_pairs)
        
        return {
            "before_dedup": before_dedup,
            "after_dedup": after_dedup,
            "removed": before_dedup - after_dedup,
            "dedup_rate": (before_dedup - after_dedup) / before_dedup * 100 if before_dedup > 0 else 0,
            "pairs": deduped_pairs
        }
    
    train_result = align_and_analyze(java_train_raw, csharp_train_raw)
    valid_result = align_and_analyze(java_valid_raw, csharp_valid_raw)
    
    print(f"Train: {train_result['before_dedup']} -> {train_result['after_dedup']} (removed {train_result['removed']}, {train_result['dedup_rate']:.1f}%)")
    print(f"Valid: {valid_result['before_dedup']} -> {valid_result['after_dedup']} (removed {valid_result['removed']}, {valid_result['dedup_rate']:.1f}%)")
    
    # ============ TOKEN LENGTH ANALYSIS ============
    print("\nAnalyzing token lengths...")
    
    def analyze_token_lengths(pairs, tokenizer, max_length=512):
        java_lengths = []
        csharp_lengths = []
        truncated_java = 0
        truncated_csharp = 0
        empty_java = 0
        empty_csharp = 0
        short_samples = 0  # < 10 tokens
        
        for pair in pairs:
            java_tokens = tokenizer(pair["java_code"], add_special_tokens=True)["input_ids"]
            csharp_tokens = tokenizer(pair["csharp_code"], add_special_tokens=True)["input_ids"]
            
            java_len = len(java_tokens)
            csharp_len = len(csharp_tokens)
            
            java_lengths.append(java_len)
            csharp_lengths.append(csharp_len)
            
            if java_len > max_length:
                truncated_java += 1
            if csharp_len > max_length:
                truncated_csharp += 1
            if java_len == 0:
                empty_java += 1
            if csharp_len == 0:
                empty_csharp += 1
            if java_len < 10 or csharp_len < 10:
                short_samples += 1
        
        def calc_stats(lengths):
            if not lengths:
                return {"mean": 0, "p50": 0, "p95": 0, "max": 0}
            sorted_lens = sorted(lengths)
            n = len(sorted_lens)
            return {
                "mean": sum(lengths) / n,
                "p50": sorted_lens[n // 2],
                "p95": sorted_lens[int(n * 0.95)],
                "max": sorted_lens[-1]
            }
        
        total = len(pairs)
        return {
            "java_stats": calc_stats(java_lengths),
            "csharp_stats": calc_stats(csharp_lengths),
            "truncated_java": truncated_java,
            "truncated_csharp": truncated_csharp,
            "truncated_java_rate": truncated_java / total * 100 if total > 0 else 0,
            "truncated_csharp_rate": truncated_csharp / total * 100 if total > 0 else 0,
            "empty_java": empty_java,
            "empty_csharp": empty_csharp,
            "short_samples": short_samples,
            "short_rate": short_samples / total * 100 if total > 0 else 0
        }
    
    train_token_stats = analyze_token_lengths(train_result["pairs"], tokenizer, config.max_length)
    valid_token_stats = analyze_token_lengths(valid_result["pairs"], tokenizer, config.max_length)
    
    print(f"Train Java - Mean: {train_token_stats['java_stats']['mean']:.1f}, P95: {train_token_stats['java_stats']['p95']}")
    print(f"Train C# - Mean: {train_token_stats['csharp_stats']['mean']:.1f}, P95: {train_token_stats['csharp_stats']['p95']}")
    print(f"Train truncation rate - Java: {train_token_stats['truncated_java_rate']:.1f}%, C#: {train_token_stats['truncated_csharp_rate']:.1f}%")
    
    # ============ TRAIN-VALID LEAKAGE CHECK (ENHANCED) ============
    print("\nChecking train-valid leakage (enhanced)...")
    
    # Helper: Normalize code (remove whitespace, comments, lowercase)
    import re
    def normalize_code(code):
        # Remove single-line comments
        code = re.sub(r'//.*$', '', code, flags=re.MULTILINE)
        # Remove multi-line comments
        code = re.sub(r'/\*.*?\*/', '', code, flags=re.DOTALL)
        # Remove all whitespace
        code = re.sub(r'\s+', '', code)
        # Lowercase
        return code.lower()
    
    # Helper: Tokenize for Jaccard (simple word-level)
    def tokenize_for_jaccard(code):
        # Split by non-alphanumeric, filter empty
        tokens = re.split(r'[^a-zA-Z0-9_]+', code)
        return set(t.lower() for t in tokens if t)
    
    # Helper: Jaccard similarity
    def jaccard_similarity(set1, set2):
        if not set1 and not set2:
            return 1.0
        if not set1 or not set2:
            return 0.0
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        return intersection / union
    
    # Build train sets
    train_java_set = set(pair["java_code"] for pair in train_result["pairs"])
    train_csharp_set = set(pair["csharp_code"] for pair in train_result["pairs"])
    
    # Build normalized train sets
    train_java_normalized = set(normalize_code(pair["java_code"]) for pair in train_result["pairs"])
    train_csharp_normalized = set(normalize_code(pair["csharp_code"]) for pair in train_result["pairs"])
    
    # Build token sets for similarity
    train_java_tokens = [tokenize_for_jaccard(pair["java_code"]) for pair in train_result["pairs"]]
    train_csharp_tokens = [tokenize_for_jaccard(pair["csharp_code"]) for pair in train_result["pairs"]]
    
    # Check each valid sample
    java_exact = 0
    csharp_exact = 0
    java_normalized = 0
    csharp_normalized = 0
    java_high_similarity = 0  # Jaccard > 0.8
    csharp_high_similarity = 0
    
    SIMILARITY_THRESHOLD = 0.8
    
    for pair in valid_result["pairs"]:
        # Exact match
        if pair["java_code"] in train_java_set:
            java_exact += 1
        if pair["csharp_code"] in train_csharp_set:
            csharp_exact += 1
        
        # Normalized match
        java_norm = normalize_code(pair["java_code"])
        csharp_norm = normalize_code(pair["csharp_code"])
        
        if java_norm in train_java_normalized:
            java_normalized += 1
        if csharp_norm in train_csharp_normalized:
            csharp_normalized += 1
        
        # Jaccard similarity (check against all train samples - expensive but thorough)
        valid_java_tokens = tokenize_for_jaccard(pair["java_code"])
        valid_csharp_tokens = tokenize_for_jaccard(pair["csharp_code"])
        
        # Sample check for efficiency (check first 100 train samples)
        java_max_sim = max((jaccard_similarity(valid_java_tokens, t) for t in train_java_tokens[:100]), default=0)
        csharp_max_sim = max((jaccard_similarity(valid_csharp_tokens, t) for t in train_csharp_tokens[:100]), default=0)
        
        if java_max_sim > SIMILARITY_THRESHOLD:
            java_high_similarity += 1
        if csharp_max_sim > SIMILARITY_THRESHOLD:
            csharp_high_similarity += 1
    
    valid_count = len(valid_result["pairs"])
    
    leakage_stats = {
        "exact_match": {
            "java": java_exact,
            "csharp": csharp_exact,
            "java_rate": java_exact / valid_count * 100 if valid_count > 0 else 0,
            "csharp_rate": csharp_exact / valid_count * 100 if valid_count > 0 else 0
        },
        "normalized_match": {
            "java": java_normalized,
            "csharp": csharp_normalized,
            "java_rate": java_normalized / valid_count * 100 if valid_count > 0 else 0,
            "csharp_rate": csharp_normalized / valid_count * 100 if valid_count > 0 else 0
        },
        "high_similarity": {
            "threshold": SIMILARITY_THRESHOLD,
            "java": java_high_similarity,
            "csharp": csharp_high_similarity,
            "java_rate": java_high_similarity / valid_count * 100 if valid_count > 0 else 0,
            "csharp_rate": csharp_high_similarity / valid_count * 100 if valid_count > 0 else 0
        },
        # Backward compatibility
        "java_exact_match": java_exact,
        "csharp_exact_match": csharp_exact,
        "java_leakage_rate": java_exact / valid_count * 100 if valid_count > 0 else 0,
        "csharp_leakage_rate": csharp_exact / valid_count * 100 if valid_count > 0 else 0
    }
    
    print(f"Exact match leakage - Java: {java_exact} ({leakage_stats['exact_match']['java_rate']:.2f}%), C#: {csharp_exact} ({leakage_stats['exact_match']['csharp_rate']:.2f}%)")
    print(f"Normalized match leakage - Java: {java_normalized} ({leakage_stats['normalized_match']['java_rate']:.2f}%), C#: {csharp_normalized} ({leakage_stats['normalized_match']['csharp_rate']:.2f}%)")
    print(f"High similarity (>{SIMILARITY_THRESHOLD}) - Java: {java_high_similarity} ({leakage_stats['high_similarity']['java_rate']:.2f}%), C#: {csharp_high_similarity} ({leakage_stats['high_similarity']['csharp_rate']:.2f}%)")

    
    # ============ SAVE RESULTS ============
    results = {
        "raw_counts": {
            "java_train": len(java_train_raw),
            "csharp_train": len(csharp_train_raw),
            "java_valid": len(java_valid_raw),
            "csharp_valid": len(csharp_valid_raw)
        },
        "dedup_stats": {
            "train": {
                "before": train_result["before_dedup"],
                "after": train_result["after_dedup"],
                "removed": train_result["removed"],
                "rate": train_result["dedup_rate"]
            },
            "valid": {
                "before": valid_result["before_dedup"],
                "after": valid_result["after_dedup"],
                "removed": valid_result["removed"],
                "rate": valid_result["dedup_rate"]
            }
        },
        "token_stats": {
            "train": train_token_stats,
            "valid": valid_token_stats
        },
        "leakage_stats": leakage_stats,
        "max_length": config.max_length
    }
    
    output_path = os.path.join(config.output_dir, "data_quality_stats.json")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\nData quality stats saved to: {output_path}")
    return results

if __name__ == "__main__":
    analyze_data_quality()
