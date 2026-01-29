#!/usr/bin/env python3
"""Analyze code style of training and test data"""
import json

train_path = r'C:\Users\Shu Leo\Desktop\practical course\LLMTrainPipeline\backend\storage\datasets\stage2 version2\train02-01.jsonl'
test_path = r'C:\Users\Shu Leo\Desktop\practical course\LLMTrainPipeline\backend\storage\datasets\stage2 version2\test02-01.jsonl'

def analyze_code_style(code):
    """Analyze code style"""
    has_def = 'def ' in code
    has_input = 'input(' in code
    has_print = 'print(' in code
    
    if has_input and has_print and not has_def:
        return 'stdin_stdout'
    elif has_def and not has_input:
        return 'function'
    else:
        return 'mixed'

print('=' * 70)
print('=== Training Data Sample Analysis (first 3) ===')
print('=' * 70)

with open(train_path, 'r', encoding='utf-8') as f:
    for i, line in enumerate(f):
        if i >= 3:
            break
        data = json.loads(line)
        code = data.get('code', '')
        style = analyze_code_style(code)
        
        print(f"\n--- Sample {i+1}: {data['id']} ---")
        print(f"source: {data.get('source')}")
        print(f"difficulty: {data.get('difficulty')}")
        print(f"Code style: {style}")
        print(f"Code content:")
        print(code)
        print()

print('=' * 70)
print('=== Statistics of the entire training set code style ===')
print('=' * 70)

stats = {'stdin_stdout': 0, 'function': 0, 'mixed': 0}
total = 0

with open(train_path, 'r', encoding='utf-8') as f:
    for line in f:
        data = json.loads(line)
        code = data.get('code', '')
        style = analyze_code_style(code)
        stats[style] += 1
        total += 1

print(f"Total training samples: {total}")
print(f"stdin/stdout script style: {stats['stdin_stdout']} ({100*stats['stdin_stdout']/total:.1f}%)")
print(f"Function definition style: {stats['function']} ({100*stats['function']/total:.1f}%)")
print(f"Mixed style: {stats['mixed']} ({100*stats['mixed']/total:.1f}%)")

print()
print('=' * 70)
print('=== Statistics of test set code style ===')
print('=' * 70)

stats_test = {'stdin_stdout': 0, 'function': 0, 'mixed': 0}
total_test = 0

with open(test_path, 'r', encoding='utf-8') as f:
    for line in f:
        data = json.loads(line)
        code = data.get('code', '')
        style = analyze_code_style(code)
        stats_test[style] += 1
        total_test += 1

print(f"Total test samples: {total_test}")
print(f"stdin/stdout script style: {stats_test['stdin_stdout']} ({100*stats_test['stdin_stdout']/total_test:.1f}%)")
print(f"Function definition style: {stats_test['function']} ({100*stats_test['function']/total_test:.1f}%)")
print(f"Mixed style: {stats_test['mixed']} ({100*stats_test['mixed']/total_test:.1f}%)")

print()
print('=' * 70)
print('=== Key Findings ===')
print('=' * 70)
print("""
Training instruction -> code mapping:
- The model learns: given a prompt, generate the corresponding code

Evaluation instruction -> generated_code mapping:
- The model needs to generate code of the same style as training to pass tests

If TACO dataset is mainly stdin/stdout style, the model should learn to generate this style of code.
Let's check if the prompt used during evaluation is consistent with training...
""")
