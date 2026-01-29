import json

# Load deduplicated aligned data
with open('xlcost_data/data/aligned/java_aligned.json', 'r', encoding='utf-8') as f:
    java_data = [json.loads(line) for line in f]
    
with open('xlcost_data/data/aligned/csharp_aligned.json', 'r', encoding='utf-8') as f:
    csharp_data = [json.loads(line) for line in f]

print(f'Java Samples: {len(java_data)}')
print(f'C# Samples: {len(csharp_data)}')
print(f'Count Match: {len(java_data) == len(csharp_data)}')

# Verify description match sample by sample
mismatch = 0
for i, (j, c) in enumerate(zip(java_data, csharp_data)):
    j_desc = j['text'].split('|')[0].strip()
    c_desc = c['text'].split('|')[0].strip()
    if j_desc != c_desc:
        mismatch += 1
        if mismatch <= 3:
            print(f'Mismatch #{i}: Java="{j_desc[:40]}..." vs C#="{c_desc[:40]}..."')

print(f'\n=== Verification Result ===')
if mismatch == 0:
    print(f'✓ Perfect Alignment! All {len(java_data)} sample pairs match description perfectly')
else:
    print(f'✗ Found {mismatch} mismatches')

# Random check 3 samples
print(f'\n=== Random Check ===')
import random
random.seed(42)
samples = random.sample(range(len(java_data)), 3)
for idx in samples:
    j_desc = java_data[idx]['text'].split('|')[0].strip()[:50]
    c_desc = csharp_data[idx]['text'].split('|')[0].strip()[:50]
    match = '✓' if j_desc == c_desc else '✗'
    print(f'{match} [{idx}] Java: {j_desc}...')
    print(f'       C#:   {c_desc}...')
