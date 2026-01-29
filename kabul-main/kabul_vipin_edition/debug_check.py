import torch
import sys
import os

print(f"Python: {sys.version}")
print(f"Torch: {torch.__version__}")
print(f"CUDA available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"Device count: {torch.cuda.device_count()}")
    print(f"Device name: {torch.cuda.get_device_name(0)}")

print("-" * 20)
print("Importing transformers...")
try:
    from transformers import Seq2SeqTrainingArguments
    print("Transformers imported successfully")
except Exception as e:
    print(f"Error importing transformers: {e}")

print(f"CUDA available after import: {torch.cuda.is_available()}")
