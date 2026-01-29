#!/usr/bin/env python3
"""
Experiment Logger - Collect experiment metadata for academic papers

Features:
- Collect environment version info (Python/PyTorch/TRL/PEFT/CUDA etc.)
- Collect hardware info (GPU model/VRAM/CPU/RAM)
- Collect LoRA training statistics (trainable params count/percentage)
- Collect dataset metadata
- Output JSON format log for backend storage

Usage:
    from experiment_logger import ExperimentLogger
    
    logger = ExperimentLogger()
    exp_log = logger.create_log(run_id="run_001", seed=42)
    # ... training process ...
    exp_log = logger.finalize(exp_log, total_steps=1000, total_tokens=512000, training_time_seconds=3600)
    logger.save_to_file(exp_log, "output/experiment_log.json")
"""

import os
import sys
import json
import platform
import subprocess
import logging
from datetime import datetime
from dataclasses import dataclass, asdict, field
from typing import Optional, Dict, Any, List

logger = logging.getLogger("ExperimentLogger")


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class EnvironmentInfo:
    """Environment version info"""
    os_version: str
    python_version: str
    pytorch_version: str
    transformers_version: str
    trl_version: Optional[str] = None
    peft_version: Optional[str] = None
    cuda_version: Optional[str] = None
    cudnn_version: Optional[str] = None
    bitsandbytes_version: Optional[str] = None


@dataclass
class HardwareInfo:
    """Hardware info"""
    gpu_model: str
    gpu_memory_gb: float
    cpu_model: str
    ram_gb: float


@dataclass
class LoraTrainStats:
    """LoRA training statistics"""
    rank: int
    alpha: int
    dropout: float
    target_modules: List[str]
    trainable_params: int
    total_params: int
    trainable_percent: float


@dataclass
class DatasetInfo:
    """Dataset metadata"""
    source: str
    train_samples: int
    total_samples: Optional[int] = None  # P0-1: Total sample count (= train + val + test or = train)
    val_samples: Optional[int] = None
    test_samples: Optional[int] = None
    total_problems: Optional[int] = None
    total_tokens: Optional[int] = None
    prompt_template: Optional[str] = None
    output_format: Optional[str] = None
    dedupe_method: Optional[str] = None
    length_filter: Optional[str] = None
    cleaning_flags: Optional[Dict[str, bool]] = None
    split_method: Optional[str] = None
    split_ratios: Optional[str] = None


@dataclass
class TrainingConfig:
    """Training config record - Paper-level complete hyperparameters"""
    batch_size: int
    gradient_accumulation_steps: int
    effective_batch_size: int
    learning_rate: str
    scheduler: str
    warmup_ratio: float
    epochs: int
    max_seq_length: int
    optimizer: str
    weight_decay: float
    max_grad_norm: Optional[float] = None
    precision: str = "fp16"
    # New: Paper-level complete record
    save_steps: Optional[int] = None
    gradient_checkpointing: bool = True
    flash_attention: bool = False
    packing: bool = False
    quantization: Optional[str] = None


@dataclass
class ExperimentLog:
    """Complete experiment log"""
    run_id: str
    start_time: str
    seed: int
    git_commit: Optional[str]
    environment: EnvironmentInfo
    hardware: HardwareInfo
    training_config: Optional[TrainingConfig] = None
    lora_stats: Optional[LoraTrainStats] = None
    dataset_info: Optional[DatasetInfo] = None
    end_time: Optional[str] = None
    total_tokens: Optional[int] = None
    total_steps: Optional[int] = None
    tokens_per_second: Optional[float] = None
    gpu_hours: Optional[float] = None
    # P1: New runtime statistics fields
    planned_steps: Optional[int] = None
    actual_steps: Optional[int] = None
    initial_lr: Optional[float] = None
    peak_gpu_memory_mb: Optional[float] = None
    steps_per_second: Optional[float] = None
    # P1: Determinism settings
    torch_deterministic: Optional[bool] = None
    cudnn_benchmark: Optional[bool] = None
    cudnn_deterministic: Optional[bool] = None
    # P2: Data quality statistics (JSON string)
    data_quality_stats_json: Optional[str] = None


# ============================================================================
# Experiment Logger Class
# ============================================================================

class ExperimentLogger:
    """Experiment log collector"""
    
    @staticmethod
    def collect_environment() -> EnvironmentInfo:
        """Collect environment version info"""
        import importlib.metadata
        
        # OS version
        os_version = f"{platform.system()} {platform.release()}"
        
        # Python version
        python_version = platform.python_version()
        
        # PyTorch version
        try:
            import torch
            pytorch_version = torch.__version__
        except ImportError:
            pytorch_version = "N/A"
        
        # Transformers version
        try:
            transformers_version = importlib.metadata.version("transformers")
        except:
            transformers_version = "N/A"
        
        # TRL version
        try:
            trl_version = importlib.metadata.version("trl")
        except:
            trl_version = None
        
        # PEFT version
        try:
            peft_version = importlib.metadata.version("peft")
        except:
            peft_version = None
        
        # CUDA version
        try:
            import torch
            cuda_version = torch.version.cuda if torch.cuda.is_available() else None
        except:
            cuda_version = None
        
        # cuDNN version
        try:
            import torch
            cudnn_version = str(torch.backends.cudnn.version()) if torch.backends.cudnn.is_available() else None
        except:
            cudnn_version = None
        
        # bitsandbytes version
        try:
            bitsandbytes_version = importlib.metadata.version("bitsandbytes")
        except:
            bitsandbytes_version = None
        
        return EnvironmentInfo(
            os_version=os_version,
            python_version=python_version,
            pytorch_version=pytorch_version,
            transformers_version=transformers_version,
            trl_version=trl_version,
            peft_version=peft_version,
            cuda_version=cuda_version,
            cudnn_version=cudnn_version,
            bitsandbytes_version=bitsandbytes_version,
        )
    
    @staticmethod
    def collect_hardware() -> HardwareInfo:
        """Collect hardware info"""
        # GPU info
        gpu_model = "N/A"
        gpu_memory_gb = 0.0
        
        try:
            import torch
            if torch.cuda.is_available():
                gpu_model = torch.cuda.get_device_name(0)
                gpu_memory_gb = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
        except:
            pass
        
        # CPU info
        cpu_model = platform.processor() or "Unknown"
        if not cpu_model or cpu_model == "Unknown":
            # Try alternative method for Windows
            try:
                if platform.system() == "Windows":
                    import winreg
                    key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 
                                         r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
                    cpu_model = winreg.QueryValueEx(key, "ProcessorNameString")[0]
                    winreg.CloseKey(key)
                else:
                    result = subprocess.run(['cat', '/proc/cpuinfo'], capture_output=True, text=True)
                    for line in result.stdout.split('\n'):
                        if 'model name' in line:
                            cpu_model = line.split(':')[1].strip()
                            break
            except:
                cpu_model = "Unknown CPU"
        
        # RAM info
        try:
            import psutil
            ram_gb = psutil.virtual_memory().total / (1024 ** 3)
        except:
            ram_gb = 0.0
        
        return HardwareInfo(
            gpu_model=gpu_model,
            gpu_memory_gb=round(gpu_memory_gb, 2),
            cpu_model=cpu_model,
            ram_gb=round(ram_gb, 2),
        )
    
    @staticmethod
    def collect_lora_stats(model) -> Optional[LoraTrainStats]:
        """Collect LoRA statistics from PEFT model"""
        try:
            from peft import PeftModel
            
            # Check if it's a PEFT model
            if not hasattr(model, 'peft_config'):
                return None
            
            # Get the first adapter config
            config = list(model.peft_config.values())[0]
            
            # Count parameters
            trainable_params = 0
            total_params = 0
            
            for name, param in model.named_parameters():
                total_params += param.numel()
                if param.requires_grad:
                    trainable_params += param.numel()
            
            trainable_percent = (trainable_params / total_params) * 100 if total_params > 0 else 0
            
            # Get target modules
            target_modules = list(config.target_modules) if hasattr(config, 'target_modules') else []
            
            return LoraTrainStats(
                rank=getattr(config, 'r', 0),
                alpha=getattr(config, 'lora_alpha', 0),
                dropout=getattr(config, 'lora_dropout', 0.0),
                target_modules=target_modules,
                trainable_params=trainable_params,
                total_params=total_params,
                trainable_percent=round(trainable_percent, 4),
            )
        except Exception as e:
            logger.warning(f"Failed to collect LoRA stats: {e}")
            return None
    
    @staticmethod
    def get_git_commit() -> Optional[str]:
        """Get current Git commit hash"""
        try:
            result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return result.stdout.strip()[:8]  # Short hash
        except:
            pass
        return None
    
    @staticmethod
    def collect_determinism_info() -> Dict[str, Any]:
        """Collect PyTorch determinism settings for reproducibility"""
        info = {}
        try:
            import torch
            info["torch_deterministic"] = torch.are_deterministic_algorithms_enabled() if hasattr(torch, 'are_deterministic_algorithms_enabled') else None
            info["cudnn_benchmark"] = torch.backends.cudnn.benchmark if hasattr(torch.backends, 'cudnn') else None
            info["cudnn_deterministic"] = torch.backends.cudnn.deterministic if hasattr(torch.backends, 'cudnn') else None
        except:
            pass
        return info
    
    @staticmethod
    def collect_training_config(config: dict) -> TrainingConfig:
        """Collect training config from config dict - Paper-level complete record"""
        training = config.get('training', {})
        lora = config.get('lora', {})
        
        batch_size = training.get('batchSize', 1)
        grad_accum = training.get('gradientAccumulation', training.get('gradAccum', 8))
        
        return TrainingConfig(
            batch_size=batch_size,
            gradient_accumulation_steps=grad_accum,
            effective_batch_size=batch_size * grad_accum,
            learning_rate=str(training.get('lr', '2e-4')),
            scheduler=training.get('scheduler', 'cosine'),
            warmup_ratio=training.get('warmupRatio', 0.03),
            epochs=training.get('epochs', 3),
            max_seq_length=training.get('maxLength', training.get('maxSeqLen', 512)),
            optimizer=training.get('optimizer', 'adamw_torch'),
            weight_decay=training.get('weightDecay', 0.01),
            max_grad_norm=training.get('maxGradNorm', 1.0),
            precision=training.get('precision', 'fp16'),
            # New fields
            save_steps=training.get('saveSteps', 100),
            gradient_checkpointing=training.get('gradientCheckpointing', True),
            flash_attention=training.get('flashAttention', False),
            packing=training.get('packing', False),
            quantization=lora.get('quantization', '4bit'),
        )
    
    @staticmethod
    def collect_dataset_info(dataset_path: str, dataset, config: dict = None) -> DatasetInfo:
        """Collect dataset metadata"""
        train_samples = len(dataset) if dataset else 0
        
        # Read max_length from config and estimate total_tokens
        max_length = 512
        if config:
            training = config.get('training', {})
            max_length = training.get('maxLength', training.get('maxSeqLen', 512))
        total_tokens = train_samples * max_length
        
        # Try to infer source from path
        source = "Unknown"
        path_lower = dataset_path.lower()
        if "leetcode" in path_lower:
            source = "LeetCode"
        elif "apps" in path_lower:
            source = "APPS"
        elif "taco" in path_lower:
            source = "TACO"
        elif "humaneval" in path_lower:
            source = "HumanEval"
        elif "mbpp" in path_lower:
            source = "MBPP"
        
        return DatasetInfo(
            source=source,
            train_samples=train_samples,
            total_samples=train_samples,  # P0-1: If no split, total = train
            total_tokens=total_tokens,
            prompt_template="system/user/assistant format",
            output_format="complete function",
        )
    
    def create_log(self, run_id: str, seed: int, config: dict = None) -> ExperimentLog:
        """Create new experiment log"""
        # Collect determinism info for P1 reproducibility
        determinism = self.collect_determinism_info()
        
        log = ExperimentLog(
            run_id=run_id,
            start_time=datetime.now().isoformat(),
            seed=seed,
            git_commit=self.get_git_commit(),
            environment=self.collect_environment(),
            hardware=self.collect_hardware(),
            torch_deterministic=determinism.get("torch_deterministic"),
            cudnn_benchmark=determinism.get("cudnn_benchmark"),
            cudnn_deterministic=determinism.get("cudnn_deterministic"),
        )
        
        if config:
            log.training_config = self.collect_training_config(config)
        
        return log
    
    def finalize(self, log: ExperimentLog, total_steps: int, 
                 total_tokens: int, training_time_seconds: float) -> ExperimentLog:
        """Update log after training completion"""
        log.end_time = datetime.now().isoformat()
        log.total_steps = total_steps
        log.total_tokens = total_tokens
        
        if training_time_seconds > 0:
            log.tokens_per_second = round(total_tokens / training_time_seconds, 2)
            log.gpu_hours = round(training_time_seconds / 3600, 4)
        
        return log
    
    def save_to_file(self, log: ExperimentLog, output_path: str):
        """Save log to JSON file"""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(asdict(log), f, indent=2, ensure_ascii=False)
        
        logger.info(f"Experiment log saved to: {output_path}")
    
    def to_json(self, log: ExperimentLog) -> str:
        """Convert to JSON string"""
        return json.dumps(asdict(log), ensure_ascii=False)
    
    def print_summary(self, log: ExperimentLog):
        """Print log summary"""
        logger.info("=" * 60)
        logger.info("EXPERIMENT SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Run ID: {log.run_id}")
        logger.info(f"Seed: {log.seed}")
        logger.info(f"Git Commit: {log.git_commit or 'N/A'}")
        logger.info("-" * 40)
        logger.info("Environment:")
        logger.info(f"  Python: {log.environment.python_version}")
        logger.info(f"  PyTorch: {log.environment.pytorch_version}")
        logger.info(f"  Transformers: {log.environment.transformers_version}")
        logger.info(f"  TRL: {log.environment.trl_version or 'N/A'}")
        logger.info(f"  PEFT: {log.environment.peft_version or 'N/A'}")
        logger.info(f"  CUDA: {log.environment.cuda_version or 'N/A'}")
        logger.info("-" * 40)
        logger.info("Hardware:")
        logger.info(f"  GPU: {log.hardware.gpu_model}")
        logger.info(f"  GPU Memory: {log.hardware.gpu_memory_gb:.2f} GB")
        logger.info(f"  CPU: {log.hardware.cpu_model}")
        logger.info(f"  RAM: {log.hardware.ram_gb:.2f} GB")
        
        if log.lora_stats:
            logger.info("-" * 40)
            logger.info("LoRA Stats:")
            logger.info(f"  Rank: {log.lora_stats.rank}")
            logger.info(f"  Alpha: {log.lora_stats.alpha}")
            logger.info(f"  Dropout: {log.lora_stats.dropout}")
            logger.info(f"  Target Modules: {log.lora_stats.target_modules}")
            logger.info(f"  Trainable Params: {log.lora_stats.trainable_params:,}")
            logger.info(f"  Total Params: {log.lora_stats.total_params:,}")
            logger.info(f"  Trainable: {log.lora_stats.trainable_percent:.4f}%")
        
        if log.total_steps:
            logger.info("-" * 40)
            logger.info("Training Stats:")
            logger.info(f"  Total Steps: {log.total_steps:,}")
            logger.info(f"  Total Tokens: {log.total_tokens:,}")
            logger.info(f"  Throughput: {log.tokens_per_second:.2f} tokens/sec")
            logger.info(f"  GPU Hours: {log.gpu_hours:.4f}")
        
        logger.info("=" * 60)


# ============================================================================
# Convenience Functions
# ============================================================================

def create_experiment_log(run_id: str, seed: int = 42, config: dict = None) -> ExperimentLog:
    """Convenience function to quickly create experiment log"""
    logger = ExperimentLogger()
    return logger.create_log(run_id, seed, config)


def output_experiment_log_event(log: ExperimentLog):
    """Output experiment log event to stdout for backend parsing"""
    print(json.dumps({
        "type": "experiment_log",
        "data": asdict(log)
    }))


if __name__ == "__main__":
    # Test code
    logging.basicConfig(level=logging.INFO)
    
    exp_logger = ExperimentLogger()
    log = exp_logger.create_log(run_id="test_run_001", seed=42)
    
    exp_logger.print_summary(log)
    
    # Simulate training completion
    log = exp_logger.finalize(log, total_steps=1000, total_tokens=512000, training_time_seconds=3600)
    
    print("\n--- JSON Output ---")
    print(exp_logger.to_json(log))
