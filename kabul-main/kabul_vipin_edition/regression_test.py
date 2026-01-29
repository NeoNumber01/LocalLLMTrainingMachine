# -*- coding: utf-8 -*-
"""
Text-to-Code Regression Test Script
Regression Test: Text-to-Code Generation (Base vs Fine-Tuned)

Purpose:
Test if the fine-tuned model capability degrades on "Natural Language -> Code" task (Catastrophic Forgetting).
Compare Base CodeT5 and Fine-Tuned CodeT5 performance on XLCoST C# dataset.

Input: "text" (NL description) in C# test.json
Output: Generate C# code and calculate BLEU/CodeBLEU
"""

import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
from datasets import load_dataset
import pandas as pd
from tqdm import tqdm
import os
import json
from datetime import datetime

# Reuse existing evaluation modules
from metrics.codebleu_eval import calculate_codebleu, calculate_bleu
from post_process import PostProcessor

# --- Configuration ---
BASE_MODEL_NAME = "Salesforce/codet5-base"
FINE_TUNED_MODEL_PATH = "./fine_tuned_codet5_java_csharp/final_model"
OUTPUT_FILE = "regression_results.csv"
SUMMARY_FILE = "regression_summary.json"
NUM_SAMPLES = 100  # Keep consistent with main evaluation, or set to None for full run
PROMPT_PREFIX = "Generate C# code: " # Prompt prefix for testing

def load_models():
    """Load both models"""
    print("Loading models...")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Running on: {device}")

    # Base Model
    print(f"Loading Base Model: {BASE_MODEL_NAME}")
    base_tok = AutoTokenizer.from_pretrained(BASE_MODEL_NAME)
    base_mod = AutoModelForSeq2SeqLM.from_pretrained(BASE_MODEL_NAME).to(device)

    # Fine-Tuned Model
    print(f"Loading Fine-Tuned Model: {FINE_TUNED_MODEL_PATH}")
    ft_tok = AutoTokenizer.from_pretrained(FINE_TUNED_MODEL_PATH, local_files_only=True)
    ft_mod = AutoModelForSeq2SeqLM.from_pretrained(FINE_TUNED_MODEL_PATH, local_files_only=True).to(device)
    
    return (base_tok, base_mod), (ft_tok, ft_mod), device

def generate_code(model, tokenizer, text, device):
    """Generate code from natural language"""
    input_text = PROMPT_PREFIX + text
    inputs = tokenizer(input_text, return_tensors="pt", truncation=True, max_length=512).to(device)
    
    with torch.no_grad():
        output = model.generate(
            input_ids=inputs["input_ids"],
            max_length=512,
            num_beams=1,
            early_stopping=False
        )
    return tokenizer.decode(output[0], skip_special_tokens=True)

def main():
    print("=" * 60)
    print("=" * 60)
    print("Text-to-Code Regression Test")
    print("=" * 60)
    print(f"Prompt Prefix: '{PROMPT_PREFIX}'")

    # 1. Load Data (Only use C# part as it contains NL -> C# mapping)
    print("\n[1/4] Loading C# Test Set...")
    try:
        dataset = load_dataset("json", data_files={"test": "xlcost_data/data/Csharp-program-level/test.json"}, split="test")
    except Exception as e:
        print(f"Error loading dataset: {e}")
        return

    if NUM_SAMPLES:
        dataset = dataset.select(range(NUM_SAMPLES))
    print(f"  Samples: {len(dataset)}")

    # 2. Load Models
    print("\n[2/4] Loading Models...")
    (base_tok, base_mod), (ft_tok, ft_mod), device = load_models()

    # 3. Generate Code
    print("\n[3/4] Executing Generation Task (Base vs Fine-Tuned)...")
    results = []
    base_preds = []
    ft_preds = []
    references = []

    processor = PostProcessor(use_formatting=True, use_healing=True)

    for item in tqdm(dataset):
        text = item['text'].split('|')[0].strip() # Extract NL description
        reference = item['code']
        
        # Base Model Generation
        base_pred = generate_code(base_mod, base_tok, text, device)
        base_pred = processor.process(base_pred) # Also post-process for fair comparison
        
        # Fine-Tuned Model Generation
        ft_pred = generate_code(ft_mod, ft_tok, text, device)
        ft_pred = processor.process(ft_pred)

        base_preds.append(base_pred)
        ft_preds.append(ft_pred)
        references.append(reference)
        
        results.append({
            "Input_Text": text,
            "Reference_Code": reference,
            "Base_Prediction": base_pred,
            "FineTuned_Prediction": ft_pred
        })

    # 4. Calculate Metrics
    print("\n[4/4] Calculating Metrics...")
    
    print("--- Base Model ---")
    base_bleu = calculate_bleu(base_preds, references)
    print(f"BLEU: {base_bleu:.2f}")
    
    print("--- Fine-Tuned Model ---")
    ft_bleu = calculate_bleu(ft_preds, references)
    print(f"BLEU: {ft_bleu:.2f}")
    
    # Try Calculate CodeBLEU (if available)
    try:
        print("\nCalculating CodeBLEU...")
        base_cb = calculate_codebleu(base_preds, references, lang="c_sharp")
        ft_cb = calculate_codebleu(ft_preds, references, lang="c_sharp")
    except Exception as e:
        print(f"CodeBLEU calculation failed: {e}")
        base_cb = {}
        ft_cb = {}

    # 5. Save Results
    print("\nSaving Results...")
    df = pd.DataFrame(results)
    df.to_csv(OUTPUT_FILE, index=False, encoding='utf-8-sig')
    
    summary = {
        "timestamp": datetime.now().isoformat(),
        "task": "text-to-code-regression",
        "prompt_prefix": PROMPT_PREFIX,
        "samples": len(dataset),
        "base_metrics": {
            "bleu": base_bleu,
            "codebleu": base_cb.get("codebleu", -1)
        },
        "fine_tuned_metrics": {
            "bleu": ft_bleu,
            "codebleu": ft_cb.get("codebleu", -1)
        }
    }
    
    with open(SUMMARY_FILE, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)

    print(f"Detailed comparison saved: {OUTPUT_FILE}")
    print(f"Summary saved: {SUMMARY_FILE}")
    
    # Print Final Conclusion
    print("\n" + "=" * 60)
    print("Regression Test Conclusion")
    print("=" * 60)
    print(f"Base Model BLEU:       {base_bleu:.2f}")
    print(f"Fine-Tuned Model BLEU: {ft_bleu:.2f}")
    diff = ft_bleu - base_bleu
    diff = ft_bleu - base_bleu
    print(f"Diff:                  {diff:+.2f}")
    
    if diff < -5.0:
        print("\n[Warning] Significant performance degradation detected (Catastrophic Forgetting)!")
        print("Fine-tuned model capability on Text-to-Code task has dropped.")
    elif diff > 0:
        print("\n[Info] Fine-tuned model improved on Text-to-code task (Positive Transfer).")
    else:
        print("\n[Info] Performance roughly equal, no serious forgetting occurred.")
    print("=" * 60)

if __name__ == "__main__":
    main()
