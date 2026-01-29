#!/usr/bin/env python3
"""
LLM 推理脚本 - 用于 Playground 功能 (支持流式输出)
使用 transformers 库加载本地模型进行推理
"""

import json
import sys
import torch
from pathlib import Path
from threading import Thread


def load_model(model_path: str):
    """加载模型和tokenizer
    
    Fixed for bitsandbytes compatibility - uses device_map='auto'
    """
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    
    print(f"Loading model from: {model_path}", file=sys.stderr)
    
    tokenizer = AutoTokenizer.from_pretrained(
        model_path,
        trust_remote_code=True,
        local_files_only=True
    )
    
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
        tokenizer.pad_token_id = tokenizer.eos_token_id
    
    # Check if we should use quantization
    quant_config = None
    try:
        import bitsandbytes
        quant_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_use_double_quant=True,
        )
    except ImportError:
        print("bitsandbytes not available, using FP16", file=sys.stderr)
    
    model_kwargs = {
        "trust_remote_code": True,
        "local_files_only": True,
        "torch_dtype": torch.float16,
        "device_map": "auto",  # Critical: avoids bitsandbytes .to() error
        "low_cpu_mem_usage": True,
    }
    if quant_config:
        model_kwargs["quantization_config"] = quant_config
    
    model = AutoModelForCausalLM.from_pretrained(model_path, **model_kwargs)
    
    print(f"Model loaded successfully", file=sys.stderr)
    return model, tokenizer


def format_messages(tokenizer, system_prompt: str, messages: list) -> str:
    """格式化消息为模型输入"""
    formatted_messages = []
    
    if system_prompt:
        formatted_messages.append({"role": "system", "content": system_prompt})
    
    for msg in messages:
        formatted_messages.append({
            "role": msg.get("role", "user"),
            "content": msg.get("content", "")
        })
    
    if hasattr(tokenizer, 'apply_chat_template'):
        try:
            return tokenizer.apply_chat_template(
                formatted_messages, tokenize=False, add_generation_prompt=True
            )
        except Exception as e:
            print(f"Warning: apply_chat_template failed: {e}", file=sys.stderr)
    
    # Fallback to ChatML format
    result = ""
    for msg in formatted_messages:
        result += f"<|im_start|>{msg['role']}\n{msg['content']}<|im_end|>\n"
    result += "<|im_start|>assistant\n"
    return result


def generate_stream(model, tokenizer, prompt: str, max_new_tokens: int = 512,
                    temperature: float = 0.7, top_p: float = 0.9,
                    repetition_penalty: float = 1.1):
    """流式生成回复 - Enhanced with repetition_penalty"""
    from transformers import TextIteratorStreamer
    
    streamer = TextIteratorStreamer(tokenizer, skip_prompt=True, skip_special_tokens=True)
    
    # Get device from model parameters (compatible with quantized models)
    device = next(model.parameters()).device
    inputs = tokenizer(prompt, return_tensors="pt")
    inputs = {k: v.to(device) for k, v in inputs.items()}
    
    do_sample = temperature > 0
    
    generation_kwargs = dict(
        **inputs,
        max_new_tokens=max_new_tokens,
        temperature=temperature if do_sample else 1.0,
        top_p=top_p if do_sample else 1.0,
        do_sample=do_sample,
        pad_token_id=tokenizer.pad_token_id,
        eos_token_id=tokenizer.eos_token_id,
        repetition_penalty=repetition_penalty,  # Reduce repetitive output
        streamer=streamer,
    )
    
    thread = Thread(target=model.generate, kwargs=generation_kwargs)
    thread.start()
    
    # Send tokens as soon as they are generated
    for new_text in streamer:
        if new_text:
            print(json.dumps({"token": new_text}), flush=True)
            
    print(json.dumps({"done": True}), flush=True)


def main():
    """主函数"""
    try:
        request = json.loads(sys.stdin.read())
        
        model_path = request.get("modelPath")
        adapter_path = request.get("adapterPath")
        system_prompt = request.get("systemPrompt", "You are a helpful assistant.")
        messages = request.get("messages", [])
        temperature = request.get("temperature", 0.7)
        max_tokens = request.get("maxTokens", 512)
        
        if not model_path:
            raise ValueError("modelPath is required")
        
        model, tokenizer = load_model(model_path)
        
        if adapter_path and Path(adapter_path).exists():
            from peft import PeftModel
            print(f"Loading adapter from: {adapter_path}", file=sys.stderr)
            model = PeftModel.from_pretrained(model, adapter_path)
        
        prompt = format_messages(tokenizer, system_prompt, messages)
        print(f"Prompt length: {len(prompt)} chars", file=sys.stderr)
        
        generate_stream(
            model, tokenizer, prompt,
            max_new_tokens=max_tokens,
            temperature=temperature
        )
        
    except Exception as e:
        import traceback
        traceback.print_exc(file=sys.stderr)
        print(json.dumps({"error": str(e)}), flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
