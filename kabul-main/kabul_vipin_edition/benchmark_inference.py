"""
Enhanced Inference Benchmark Script
Measures inference latency (tokenization + generation separately), throughput, VRAM usage
with detailed statistics for paper-ready reporting
"""
import json
import os
import time
import subprocess
import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
from train_config import TrainingConfig

def get_nvidia_smi_vram():
    """Get VRAM usage from nvidia-smi for comparison"""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            encoding='utf-8',
            errors='replace',
            timeout=10
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split(',')
            return {
                "used_mb": int(parts[0].strip()),
                "total_mb": int(parts[1].strip())
            }
    except:
        pass
    return None

def calc_percentile(data, p):
    """Calculate percentile"""
    if not data:
        return 0
    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * p / 100
    f = int(k)
    c = f + 1 if f + 1 < len(sorted_data) else f
    return sorted_data[f] + (sorted_data[c] - sorted_data[f]) * (k - f)

def benchmark_inference():
    config = TrainingConfig()
    model_path = os.path.join(config.output_dir, "final_model")
    
    if not os.path.exists(model_path):
        print(f"Error: Model not found at {model_path}")
        return None
    
    print(f"Loading model from {model_path}...")
    tokenizer = AutoTokenizer.from_pretrained(model_path)
    model = AutoModelForSeq2SeqLM.from_pretrained(model_path)
    
    # Determine device and FP16 status
    device = "cuda" if torch.cuda.is_available() else "cpu"
    use_fp16 = torch.cuda.is_available()  # Check if we can use FP16
    
    model = model.to(device)
    model.eval()
    
    # Check actual dtype
    model_dtype = next(model.parameters()).dtype
    
    print(f"Device: {device}")
    print(f"Model dtype: {model_dtype}")
    if device == "cuda":
        print(f"GPU: {torch.cuda.get_device_name(0)}")
    
    # Load test samples
    def load_json(path):
        data = []
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            try:
                data = json.loads(content)
                if isinstance(data, list):
                    return data
            except json.JSONDecodeError:
                pass
            lines = content.split('\n')
            for line in lines:
                if line.strip():
                    try:
                        data.append(json.loads(line))
                    except:
                        pass
        return data
    
    valid_data = load_json(config.java_valid_path)
    test_samples = [item['code'] for item in valid_data[:50]]  # 50 samples
    
    print(f"\nBenchmarking with {len(test_samples)} samples...")
    
    prefix = "translate Java to C#: "
    
    # ============ WARMUP ============
    print("\n0. Warming up...")
    for _ in range(3):
        inputs = tokenizer(prefix + test_samples[0], return_tensors="pt", max_length=512, truncation=True)
        inputs = {k: v.to(device) for k, v in inputs.items()}
        with torch.no_grad():
            model.generate(**inputs, max_length=512, num_beams=1)
    
    # Clear VRAM stats after warmup
    if device == "cuda":
        torch.cuda.reset_peak_memory_stats()
        torch.cuda.synchronize()
    
    # ============ DETAILED LATENCY MEASUREMENT ============
    print("\n1. Detailed Latency Measurement (Greedy, batch=1)...")
    
    tokenization_times = []
    generation_times = []
    total_times = []
    input_token_lengths = []
    output_token_lengths = []
    
    for sample in test_samples:
        input_text = prefix + sample
        
        # Tokenization timing
        if device == "cuda":
            torch.cuda.synchronize()
        tok_start = time.perf_counter()
        inputs = tokenizer(input_text, return_tensors="pt", max_length=512, truncation=True)
        inputs = {k: v.to(device) for k, v in inputs.items()}
        if device == "cuda":
            torch.cuda.synchronize()
        tok_end = time.perf_counter()
        
        input_len = inputs["input_ids"].shape[1]
        input_token_lengths.append(input_len)
        
        # Generation timing
        gen_start = time.perf_counter()
        with torch.no_grad():
            output = model.generate(**inputs, max_length=512, num_beams=1, do_sample=False)
        if device == "cuda":
            torch.cuda.synchronize()
        gen_end = time.perf_counter()
        
        output_len = output.shape[1]
        output_token_lengths.append(output_len)
        
        tok_time = (tok_end - tok_start) * 1000
        gen_time = (gen_end - gen_start) * 1000
        
        tokenization_times.append(tok_time)
        generation_times.append(gen_time)
        total_times.append(tok_time + gen_time)
    
    # Calculate statistics
    def calc_stats(data):
        if not data:
            return {}
        return {
            "mean": sum(data) / len(data),
            "min": min(data),
            "max": max(data),
            "p50": calc_percentile(data, 50),
            "p95": calc_percentile(data, 95),
            "p99": calc_percentile(data, 99)
        }
    
    tok_stats = calc_stats(tokenization_times)
    gen_stats = calc_stats(generation_times)
    total_stats = calc_stats(total_times)
    input_len_stats = calc_stats(input_token_lengths)
    output_len_stats = calc_stats(output_token_lengths)
    
    print(f"   Tokenization: mean={tok_stats['mean']:.1f}ms, P50={tok_stats['p50']:.1f}ms, P95={tok_stats['p95']:.1f}ms")
    print(f"   Generation: mean={gen_stats['mean']:.1f}ms, P50={gen_stats['p50']:.1f}ms, P95={gen_stats['p95']:.1f}ms")
    print(f"   Total (E2E): mean={total_stats['mean']:.1f}ms, P50={total_stats['p50']:.1f}ms, P95={total_stats['p95']:.1f}ms")
    print(f"   Input tokens: mean={input_len_stats['mean']:.0f}, P50={input_len_stats['p50']:.0f}, P95={input_len_stats['p95']:.0f}")
    print(f"   Output tokens: mean={output_len_stats['mean']:.0f}, P50={output_len_stats['p50']:.0f}, P95={output_len_stats['p95']:.0f}")
    
    # ============ GPU VRAM MEASUREMENT ============
    print("\n2. GPU VRAM Usage...")
    
    if device == "cuda":
        # PyTorch measurement
        peak_vram_bytes = torch.cuda.max_memory_allocated()
        peak_vram_mb = peak_vram_bytes / (1024 ** 2)
        peak_vram_gb = peak_vram_bytes / (1024 ** 3)
        
        # nvidia-smi measurement
        nvidia_smi = get_nvidia_smi_vram()
        
        print(f"   PyTorch max_memory_allocated: {peak_vram_mb:.1f} MB ({peak_vram_gb:.2f} GB)")
        if nvidia_smi:
            print(f"   nvidia-smi used: {nvidia_smi['used_mb']} MB / {nvidia_smi['total_mb']} MB")
    else:
        peak_vram_mb = 0
        peak_vram_gb = 0
        nvidia_smi = None
        print("   VRAM: N/A (CPU mode)")
    
    # ============ BATCH THROUGHPUT ============
    print("\n3. Batch Throughput...")
    
    batch_sizes = [1, 4, 8] if device == "cuda" else [1, 2]
    throughput_results = {}
    
    for batch_size in batch_sizes:
        batch_texts = [prefix + s for s in test_samples[:batch_size * 5]]
        total_samples = len(batch_texts)
        
        if device == "cuda":
            torch.cuda.synchronize()
        start = time.perf_counter()
        
        for i in range(0, total_samples, batch_size):
            batch = batch_texts[i:i+batch_size]
            inputs = tokenizer(batch, return_tensors="pt", max_length=512, truncation=True, padding=True)
            inputs = {k: v.to(device) for k, v in inputs.items()}
            
            with torch.no_grad():
                model.generate(**inputs, max_length=512, num_beams=1)
        
        if device == "cuda":
            torch.cuda.synchronize()
        end = time.perf_counter()
        
        throughput = total_samples / (end - start)
        throughput_results[batch_size] = throughput
        print(f"   Batch size {batch_size}: {throughput:.2f} samples/s")
    
    # ============ GREEDY vs BEAM SEARCH ============
    print("\n4. Greedy vs Beam Search (fixed sample)...")
    
    # Use median-length sample for fair comparison
    median_idx = len(test_samples) // 2
    test_sample = test_samples[median_idx]
    inputs = tokenizer(prefix + test_sample, return_tensors="pt", max_length=512, truncation=True)
    inputs = {k: v.to(device) for k, v in inputs.items()}
    fixed_input_len = inputs["input_ids"].shape[1]
    
    greedy_times = []
    beam_times = []
    
    # Greedy (num_beams=1)
    for _ in range(5):
        if device == "cuda":
            torch.cuda.synchronize()
        start = time.perf_counter()
        with torch.no_grad():
            greedy_output = model.generate(**inputs, max_length=512, num_beams=1, do_sample=False)
        if device == "cuda":
            torch.cuda.synchronize()
        greedy_times.append((time.perf_counter() - start) * 1000)
    
    # Beam Search (num_beams=4)
    for _ in range(5):
        if device == "cuda":
            torch.cuda.synchronize()
        start = time.perf_counter()
        with torch.no_grad():
            beam_output = model.generate(**inputs, max_length=512, num_beams=4, do_sample=False)
        if device == "cuda":
            torch.cuda.synchronize()
        beam_times.append((time.perf_counter() - start) * 1000)
    
    avg_greedy = sum(greedy_times) / len(greedy_times)
    avg_beam = sum(beam_times) / len(beam_times)
    
    greedy_text = tokenizer.decode(greedy_output[0], skip_special_tokens=True)
    beam_text = tokenizer.decode(beam_output[0], skip_special_tokens=True)
    
    print(f"   Fixed input length: {fixed_input_len} tokens")
    print(f"   Greedy (num_beams=1): {avg_greedy:.1f} ms")
    print(f"   Beam Search (num_beams=4): {avg_beam:.1f} ms")
    print(f"   Beam overhead: {(avg_beam/avg_greedy - 1)*100:.1f}%")
    print(f"   Output identical: {greedy_text == beam_text}")
    
    # ============ SAVE RESULTS ============
    results = {
        "device": device,
        "gpu_name": torch.cuda.get_device_name(0) if device == "cuda" else "CPU",
        "model_dtype": str(model_dtype),
        "fp16_enabled": model_dtype == torch.float16,
        "max_length": 512,
        "num_beams_default": 1,
        "samples_measured": len(test_samples),
        
        "latency": {
            "tokenization": tok_stats,
            "generation": gen_stats,
            "total_e2e": total_stats
        },
        
        "token_lengths": {
            "input": input_len_stats,
            "output": output_len_stats
        },
        
        "vram": {
            "pytorch_peak_mb": peak_vram_mb,
            "pytorch_peak_gb": peak_vram_gb,
            "nvidia_smi": nvidia_smi,
            "measurement_method": "torch.cuda.max_memory_allocated()"
        },
        
        "batch_throughput": {
            str(k): v for k, v in throughput_results.items()
        },
        
        "decoding_comparison": {
            "fixed_input_tokens": fixed_input_len,
            "greedy_ms": avg_greedy,
            "beam4_ms": avg_beam,
            "beam_overhead_percent": (avg_beam/avg_greedy - 1)*100,
            "output_identical": greedy_text == beam_text
        }
    }
    
    output_path = os.path.join(config.output_dir, "inference_benchmark.json")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\nResults saved to: {output_path}")
    return results

if __name__ == "__main__":
    benchmark_inference()
