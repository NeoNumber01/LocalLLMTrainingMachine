import os
import json
import time
import psutil
import platform
import torch
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

class TrainingReporter:
    def __init__(self, output_dir: str, config: Any):
        self.output_dir = output_dir
        self.config = config
        self.start_time = time.time()
        self.history = {
            "system_info": self._get_system_info(),
            "config": self._get_config_dict(config),
            "data_stats": {},
            "epochs": []
        }
        self.current_epoch_data = {"epoch": 0, "steps": []}
        
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)

    def _get_system_info(self) -> Dict[str, Any]:
        info = {
            "os": platform.platform(),
            "python_version": platform.python_version(),
            "pytorch_version": torch.__version__,
            "cpu": platform.processor(),
            "ram_gb": round(psutil.virtual_memory().total / (1024**3), 2)
        }
        
        # Get transformers version
        try:
            import transformers
            info["transformers_version"] = transformers.__version__
        except:
            info["transformers_version"] = "unknown"
        
        if torch.cuda.is_available():
            info["gpu_name"] = torch.cuda.get_device_name(0)
            info["gpu_count"] = torch.cuda.device_count()
            info["gpu_memory_gb"] = round(torch.cuda.get_device_properties(0).total_memory / (1024**3), 2)
            info["cuda_version"] = torch.version.cuda
        else:
            info["gpu_name"] = "None (CPU only)"
            info["cuda_version"] = "N/A"
            
        return info

    def _get_config_dict(self, config: Any) -> Dict[str, Any]:
        return {k: v for k, v in config.__dict__.items() if not k.startswith('_')}

    def set_data_stats(self, train_samples: int, valid_samples: int, 
                       train_before_dedup: int = None, valid_before_dedup: int = None):
        """Record dataset statistics"""
        self.history["data_stats"] = {
            "train_samples": train_samples,
            "valid_samples": valid_samples,
            "train_before_dedup": train_before_dedup,
            "valid_before_dedup": valid_before_dedup,
            "train_dedup_removed": (train_before_dedup - train_samples) if train_before_dedup else None,
            "valid_dedup_removed": (valid_before_dedup - valid_samples) if valid_before_dedup else None,
        }

    def set_model_info(self, model):
        """Record model architecture information"""
        total_params = sum(p.numel() for p in model.parameters())
        trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
        
        self.history["model_info"] = {
            "total_parameters": total_params,
            "trainable_parameters": trainable_params,
            "frozen_parameters": total_params - trainable_params,
            "model_size_mb": round(total_params * 4 / (1024 * 1024), 2),  # Assuming float32
        }

    def log_step(self, step: int, loss: float, learning_rate: float):
        self.current_epoch_data["steps"].append({
            "step": step,
            "loss": loss,
            "lr": learning_rate,
            "timestamp": time.time()
        })

    def on_epoch_end(self, epoch: int, eval_loss: float, metrics: Dict[str, float] = None):
        epoch_info = {
            "epoch": epoch,
            "avg_train_loss": sum(s["loss"] for s in self.current_epoch_data["steps"]) / len(self.current_epoch_data["steps"]) if self.current_epoch_data["steps"] else 0,
            "eval_loss": eval_loss,
            "duration_seconds": time.time() - self.current_epoch_data.get("start_time", self.start_time),
            "step_data": self.current_epoch_data["steps"]
        }
        
        if metrics:
            epoch_info.update(metrics)
            
        self.history["epochs"].append(epoch_info)
        
        # Reset for next epoch
        self.current_epoch_data = {"epoch": epoch + 1, "steps": [], "start_time": time.time()}
        
        # Save intermediate logs
        self.save_logs()

    def save_logs(self):
        log_path = os.path.join(self.output_dir, "training_logs.json")
        with open(log_path, 'w', encoding='utf-8') as f:
            json.dump(self.history, f, indent=2, ensure_ascii=False)

    def generate_report(self):
        """Generates a comprehensive Markdown report for research paper"""
        self.save_logs()
        
        report_path = os.path.join(self.output_dir, "train_report.md")
        
        duration = str(timedelta(seconds=int(time.time() - self.start_time)))
        best_loss = min([e["eval_loss"] for e in self.history["epochs"]]) if self.history["epochs"] else "N/A"
        
        # Get data stats
        data_stats = self.history.get("data_stats", {})
        model_info = self.history.get("model_info", {})
        
        md = f"""# CodeT5 Java to C# Translation - Training Report

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**Total Training Duration:** {duration}  
**Best Validation Loss:** {best_loss}

---

## 1. System Environment

| Component | Details |
|-----------|---------|
| GPU | {self.history['system_info']['gpu_name']} |
| VRAM | {self.history['system_info'].get('gpu_memory_gb', 'N/A')} GB |
| CUDA Version | {self.history['system_info'].get('cuda_version', 'N/A')} |
| CPU | {self.history['system_info']['cpu']} |
| RAM | {self.history['system_info']['ram_gb']} GB |
| OS | {self.history['system_info']['os']} |
| Python | {self.history['system_info']['python_version']} |
| PyTorch | {self.history['system_info']['pytorch_version']} |
| Transformers | {self.history['system_info'].get('transformers_version', 'N/A')} |

---

## 2. Dataset Statistics

| Metric | Training Set | Validation Set |
|--------|-------------|----------------|
| Samples (after dedup) | {data_stats.get('train_samples', 'N/A')} | {data_stats.get('valid_samples', 'N/A')} |
| Samples (before dedup) | {data_stats.get('train_before_dedup', 'N/A')} | {data_stats.get('valid_before_dedup', 'N/A')} |
| Duplicates Removed | {data_stats.get('train_dedup_removed', 'N/A')} | {data_stats.get('valid_dedup_removed', 'N/A')} |

**Data Source:**
- Java: `{self.config.java_train_path}`
- C#: `{self.config.csharp_train_path}`

---

## 3. Model Configuration

### 3.1 Base Model
| Parameter | Value |
|-----------|-------|
| Model Name | `{self.config.base_model}` |
| Total Parameters | {model_info.get('total_parameters', 'N/A'):,} |
| Trainable Parameters | {model_info.get('trainable_parameters', 'N/A'):,} |
| Model Size | {model_info.get('model_size_mb', 'N/A')} MB |

### 3.2 Training Hyperparameters
| Parameter | Value |
|-----------|-------|
| Learning Rate | {self.config.learning_rate} |
| Batch Size (per device) | {self.config.per_device_train_batch_size} |
| Gradient Accumulation Steps | {self.config.gradient_accumulation_steps} |
| Effective Batch Size | {self.config.per_device_train_batch_size * self.config.gradient_accumulation_steps} |
| Number of Epochs | {self.config.num_train_epochs} |
| Weight Decay | {self.config.weight_decay} |
| Warmup Steps | {self.config.warmup_steps} |
| Max Sequence Length | {self.config.max_length} |
| Mixed Precision (FP16) | {'Enabled' if self.config.fp16 else 'Disabled'} |

---

## 4. Training Results

### 4.1 Per-Epoch Metrics

| Epoch | Train Loss | Eval Loss | Duration |
|-------|------------|-----------|----------|
"""
        
        for e in self.history["epochs"]:
            md += f"| {e['epoch']} | {e['avg_train_loss']:.4f} | {e['eval_loss']:.4f} | {e['duration_seconds']:.1f}s |\n"
        
        # Pre-compute values for f-string (ternary with format specifier doesn't work directly)
        initial_loss = f"{self.history['epochs'][0]['avg_train_loss']:.4f}" if self.history['epochs'] else 'N/A'
        final_loss = f"{self.history['epochs'][-1]['avg_train_loss']:.4f}" if self.history['epochs'] else 'N/A'
        
        md += f"""
### 4.2 Training Progress Summary

- **Initial Loss:** {initial_loss}
- **Final Loss:** {final_loss}
- **Best Eval Loss:** {best_loss}


---

## 5. Output Files

| File | Description |
|------|-------------|
| `{self.output_dir}/final_model/` | Saved model weights and tokenizer |
| `{self.output_dir}/training_logs.json` | Detailed step-level training logs (for plotting) |
| `{self.output_dir}/train_report.md` | This report |

---

> **Note:** For custom visualization, use the `training_logs.json` file which contains step-level loss and learning rate data.
"""
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(md)
            
        print(f"\n{'='*60}")
        print(f"Training Report generated at: {report_path}")
        print(f"Training Logs saved at: {os.path.join(self.output_dir, 'training_logs.json')}")
        print(f"{'='*60}")

