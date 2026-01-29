#!/usr/bin/env python3
"""分析训练数据和测试数据的代码风格"""
import json

train_path = r'C:\Users\Shu Leo\Desktop\practical course\LLMTrainPipeline\backend\storage\datasets\stage2 version2\train02-01.jsonl'
test_path = r'C:\Users\Shu Leo\Desktop\practical course\LLMTrainPipeline\backend\storage\datasets\stage2 version2\test02-01.jsonl'

def analyze_code_style(code):
    """分析代码风格"""
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
print('=== 训练数据样本分析 (前3条) ===')
print('=' * 70)

with open(train_path, 'r', encoding='utf-8') as f:
    for i, line in enumerate(f):
        if i >= 3:
            break
        data = json.loads(line)
        code = data.get('code', '')
        style = analyze_code_style(code)
        
        print(f"\n--- 样本 {i+1}: {data['id']} ---")
        print(f"source: {data.get('source')}")
        print(f"difficulty: {data.get('difficulty')}")
        print(f"代码风格: {style}")
        print(f"代码内容:")
        print(code)
        print()

print('=' * 70)
print('=== 统计整个训练集的代码风格 ===')
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

print(f"总训练样本数: {total}")
print(f"stdin/stdout 脚本风格: {stats['stdin_stdout']} ({100*stats['stdin_stdout']/total:.1f}%)")
print(f"函数定义风格: {stats['function']} ({100*stats['function']/total:.1f}%)")
print(f"混合风格: {stats['mixed']} ({100*stats['mixed']/total:.1f}%)")

print()
print('=' * 70)
print('=== 统计测试集的代码风格 ===')
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

print(f"总测试样本数: {total_test}")
print(f"stdin/stdout 脚本风格: {stats_test['stdin_stdout']} ({100*stats_test['stdin_stdout']/total_test:.1f}%)")
print(f"函数定义风格: {stats_test['function']} ({100*stats_test['function']/total_test:.1f}%)")
print(f"混合风格: {stats_test['mixed']} ({100*stats_test['mixed']/total_test:.1f}%)")

print()
print('=' * 70)
print('=== 关键发现 ===')
print('=' * 70)
print("""
训练时的 instruction -> code 映射:
- 模型学习的是：给定 prompt，生成相应的 code

评测时的 instruction -> generated_code 映射:
- 模型需要生成和训练时相同风格的代码才能通过测试

如果 TACO 数据集主要是 stdin/stdout 风格，模型应该学会生成这种风格的代码。
让我们检查评测时使用的 prompt 是否和训练时一致...
""")
