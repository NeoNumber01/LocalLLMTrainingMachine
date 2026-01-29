#!/usr/bin/env python3
"""
Merge LoRA adapter into base model.

This script merges a PEFT LoRA adapter with its base model,
creating a standalone model that can be used without loading adapters.

Usage:
    python merge_adapter.py --base_model <path> --adapter <path> --output <path> [--quantization <4bit|8bit>]
"""

import argparse
import json
import sys
import os
import gc

def main():
    parser = argparse.ArgumentParser(description='Merge LoRA adapter into base model')
    parser.add_argument('--base_model', required=True, help='Path to base model')
    parser.add_argument('--adapter', required=True, help='Path to LoRA adapter')
    parser.add_argument('--output', required=True, help='Output path for merged model')
    parser.add_argument('--quantization', choices=['4bit', '8bit', 'none'], default='none',
                        help='Quantization to use when loading (default: none)')
    
    args = parser.parse_args()
    
    # 输出状态给调用者
    def log_status(status, message, progress=None):
        output = {"status": status, "message": message}
        if progress is not None:
            output["progress"] = progress
        print(json.dumps(output), flush=True)
    
    try:
        log_status("running", "Importing libraries...", 5)
        
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
        from peft import PeftModel
        
        log_status("running", f"Loading base model from {args.base_model}...", 10)
        
        # 准备加载配置
        model_kwargs = {
            "trust_remote_code": True,
            "torch_dtype": torch.float16,
            "device_map": "auto",
            "low_cpu_mem_usage": True,
        }
        
        # 如果使用量化，设置配置（但合并时推荐不使用量化）
        if args.quantization == '4bit':
            log_status("running", "Using 4-bit quantization for loading...", 12)
            model_kwargs["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.float16,
            )
        elif args.quantization == '8bit':
            log_status("running", "Using 8-bit quantization for loading...", 12)
            model_kwargs["quantization_config"] = BitsAndBytesConfig(load_in_8bit=True)
        
        # 加载基础模型
        model = AutoModelForCausalLM.from_pretrained(args.base_model, **model_kwargs)
        
        log_status("running", "Loading tokenizer...", 30)
        tokenizer = AutoTokenizer.from_pretrained(args.base_model, trust_remote_code=True)
        
        log_status("running", f"Loading LoRA adapter from {args.adapter}...", 40)
        model = PeftModel.from_pretrained(model, args.adapter)
        
        log_status("running", "Merging adapter into base model...", 50)
        
        # 执行合并
        model = model.merge_and_unload()
        
        log_status("running", f"Saving merged model to {args.output}...", 70)
        
        # 确保输出目录存在
        os.makedirs(args.output, exist_ok=True)
        
        # 保存合并后的模型
        model.save_pretrained(args.output, safe_serialization=True)
        tokenizer.save_pretrained(args.output)
        
        log_status("running", "Cleaning up...", 95)
        
        # 清理内存
        del model
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        
        log_status("success", f"Merged model saved to {args.output}", 100)
        
    except Exception as e:
        log_status("error", str(e))
        sys.exit(1)

if __name__ == "__main__":
    main()
