from train_config import TrainingConfig
from train_data import JavaCSharpDataset
from transformers import AutoTokenizer
import torch
import sys

def verify():
    print("=== Training Setup Verification ===")
    
    # 1. Check Imports and Device
    try:
        config = TrainingConfig()
        print(f"✔ Config loaded. Target device: {config.device}")
        if config.device == 'cuda':
            print(f"  CUDA Device: {torch.cuda.get_device_name(0)}")
            print(f"  VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB")
    except Exception as e:
        print(f"✘ Config/Device validation failed: {e}")
        return

    # 2. Check Tokenizer
    try:
        print(f"Loading tokenizer: {config.base_model}...")
        tokenizer = AutoTokenizer.from_pretrained(config.base_model)
        print("✔ Tokenizer loaded.")
    except Exception as e:
        print(f"✘ Tokenizer loading failed: {e}")
        return

    # 3. Check Data Loading & Alignment
    try:
        print("Testing data alignment and loading (this may take a moment)...")
        dataset = JavaCSharpDataset(config, tokenizer)
        
        # Test just the alignment logic on train set (not full preprocessing yet to fail fast if key mismatch)
        pairs = dataset.align_data(config.java_train_path, config.csharp_train_path)
        
        if len(pairs) == 0:
            print("✘ Error: No aligned pairs found! Check if dataset paths and descriptions match.")
            return
            
        print(f"✔ Alignment success! Found {len(pairs)} pairs.")
        print("Sample pair:")
        print(f"  Description: {pairs[0].get('description', 'N/A')[:50]}...")
        print(f"  Java (len): {len(pairs[0]['java_code'])}")
        print(f"  C# (len): {len(pairs[0]['csharp_code'])}")
        
        # Test full preprocessing on a small subset
        print("Testing tokenization on top 5 samples...")
        dataset.config = config # Ensure config is attached if not already
        subset = dataset.preprocess_function({
            "java_code": [p["java_code"] for p in pairs[:5]],
            "csharp_code": [p["csharp_code"] for p in pairs[:5]]
        })
        print("✔ Tokenization success.")
        print(f"  Input IDs shape: {len(subset['input_ids'])} x {len(subset['input_ids'][0])}")
        
    except FileNotFoundError as e:
        print(f"✘ Data file not found: {e}")
        return
    except Exception as e:
        print(f"✘ Data validation failed: {e}")
        import traceback
        traceback.print_exc()
        return

    print("\nSUCCESS: All systems ready for training.")
    print("You can now run: python train_model.py")

if __name__ == "__main__":
    verify()
