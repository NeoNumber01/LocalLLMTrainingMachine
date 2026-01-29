# -*- coding: utf-8 -*-
"""
Dataset Alignment Script
Align Java and C# test datasets by matching on description text

Problem Analysis:
- Java: 911 samples, C#: 899 samples
- Common descriptions: 759 unique descriptions
- Duplicates: Java=146, C#=140
- Direct index matching only correct for 72/899

Solution:
Match strictly by exact description text (text field) to generate aligned datasets.
"""

import json
from collections import defaultdict
import os

def load_jsonl(filepath):
    """Load JSON Lines file"""
    data = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                data.append(json.loads(line))
    return data

def save_jsonl(data, filepath):
    """Save as JSON Lines file"""
    with open(filepath, 'w', encoding='utf-8') as f:
        for item in data:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')

def get_description(item):
    """Extract problem description as matching key"""
    return item['text'].split('|')[0].strip()

def align_datasets(java_path, csharp_path, output_dir):
    """
    Align Java and C# datasets
    
    Strategy: Exact match by description text, maintaining order
    """
    print("=" * 60)
    print("Starting Dataset Alignment")
    print("=" * 60)
    
    # Load data
    java_data = load_jsonl(java_path)
    csharp_data = load_jsonl(csharp_path)
    
    print(f"\nOriginal Data:")
    print(f"  Java Samples: {len(java_data)}")
    print(f"  C# Samples: {len(csharp_data)}")
    
    # Group by description
    java_by_desc = defaultdict(list)
    for i, item in enumerate(java_data):
        desc = get_description(item)
        java_by_desc[desc].append({'index': i, 'item': item})
    
    csharp_by_desc = defaultdict(list)
    for i, item in enumerate(csharp_data):
        desc = get_description(item)
        csharp_by_desc[desc].append({'index': i, 'item': item})
    
    # Statistics
    java_unique = set(java_by_desc.keys())
    csharp_unique = set(csharp_by_desc.keys())
    common_descs = java_unique & csharp_unique
    only_java = java_unique - csharp_unique
    only_csharp = csharp_unique - java_unique
    
    print(f"\nDescription Statistics:")
    print(f"  Java Unique Descs: {len(java_unique)}")
    print(f"  C# Unique Descs: {len(csharp_unique)}")
    print(f"  Common Descriptions: {len(common_descs)}")
    print(f"  Only in Java: {len(only_java)}")
    print(f"  Only in C#: {len(only_csharp)}")
    
    # Perform alignment
    aligned_java = []
    aligned_csharp = []
    alignment_log = []
    
    # Order by common descriptions (using original Java order)
    processed_descs = set()
    
    for i, java_item in enumerate(java_data):
        desc = get_description(java_item)
        
        # Skip descriptions only in Java
        if desc not in csharp_by_desc:
            continue
        
        # Skip already processed descriptions (handle duplicates)
        if desc in processed_descs:
            continue
        
        java_list = java_by_desc[desc]
        csharp_list = csharp_by_desc[desc]
        
        # Match using the minimum count from both sides
        match_count = min(len(java_list), len(csharp_list))
        
        for k in range(match_count):
            aligned_java.append(java_list[k]['item'])
            aligned_csharp.append(csharp_list[k]['item'])
            alignment_log.append({
                'description': desc[:80],
                'java_original_idx': java_list[k]['index'],
                'csharp_original_idx': csharp_list[k]['index'],
            })
        
        processed_descs.add(desc)
    
    print(f"\nAlignment Results:")
    print(f"  Aligned Samples: {len(aligned_java)}")
    print(f"  Dropped Java Samples: {len(java_data) - len(aligned_java)}")
    print(f"  Dropped C# Samples: {len(csharp_data) - len(aligned_csharp)}")
    
    # Verify alignment
    mismatch_count = 0
    for i, (j, c) in enumerate(zip(aligned_java, aligned_csharp)):
        j_desc = get_description(j)
        c_desc = get_description(c)
        if j_desc != c_desc:
            mismatch_count += 1
            if mismatch_count <= 3:
                print(f"  Warning: Index {i} mismatch:")
                print(f"    Java: {j_desc[:50]}...")
                print(f"    C#: {c_desc[:50]}...")
    
    if mismatch_count == 0:
        print(f"  ✓ Verification Passed: All {len(aligned_java)} pairs match descriptions perfectly.")
    else:
        print(f"  ✗ Verification Failed: {mismatch_count} mismatches found.")
    
    # Save aligned data
    os.makedirs(output_dir, exist_ok=True)
    
    java_output = os.path.join(output_dir, 'java_aligned.json')
    csharp_output = os.path.join(output_dir, 'csharp_aligned.json')
    log_output = os.path.join(output_dir, 'alignment_log.json')
    
    save_jsonl(aligned_java, java_output)
    save_jsonl(aligned_csharp, csharp_output)
    
    with open(log_output, 'w', encoding='utf-8') as f:
        json.dump({
            'total_aligned': len(aligned_java),
            'java_original': len(java_data),
            'csharp_original': len(csharp_data),
            'common_descriptions': len(common_descs),
            'only_java_descriptions': list(only_java),
            'only_csharp_descriptions': list(only_csharp),
            'alignments': alignment_log
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\nOutput files:")
    print(f"  Java (Aligned): {java_output}")
    print(f"  C# (Aligned): {csharp_output}")
    print(f"  Alignment Log: {log_output}")
    print("=" * 60)
    
    return len(aligned_java)

if __name__ == "__main__":
    java_path = "xlcost_data/data/Java-program-level/test.json"
    csharp_path = "xlcost_data/data/Csharp-program-level/test.json"
    output_dir = "xlcost_data/data/aligned"
    
    align_datasets(java_path, csharp_path, output_dir)
