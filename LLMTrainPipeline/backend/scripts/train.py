#!/usr/bin/env python3
"""
LLM Training Script with TRL SFTTrainer + QLoRA
Optimized based on LeoLLM successful practices

Usage: python train.py --config config.json

Key improvements:
- Uses TRL SFTTrainer with messages format (automatic loss masking)
- Fixed bitsandbytes compatibility issues
- Auto-adjusts parameters for small datasets
- Better 4-bit quantization handling
"""

import os
import sys
import gc

# Set PyTorch memory allocation config to avoid fragmentation
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
import json
import argparse
import logging
import time
from pathlib import Path
from datetime import datetime
from dataclasses import asdict

# Import experiment logger for academic-grade logging
from experiment_logger import ExperimentLogger, output_experiment_log_event

import torch
from datasets import Dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TrainerCallback,
)
from peft import (
    LoraConfig,
    get_peft_model,
    prepare_model_for_kbit_training,
    TaskType,
)


# ============================================================================
# Logging Configuration
# ============================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("SFTTrainer")


# ============================================================================
# Check TRL and bitsandbytes availability
# ============================================================================
def check_trl_available():
    """Check if TRL is available."""
    try:
        from trl import SFTTrainer, SFTConfig
        import importlib.metadata
        version = importlib.metadata.version("trl")
        logger.info(f"TRL version: {version}")
        return True
    except ImportError:
        logger.warning("TRL not available, will use fallback Trainer")
        return False


def check_bitsandbytes_version():
    """Check bitsandbytes version and return compatibility info."""
    try:
        import bitsandbytes as bnb
        import importlib.metadata
        version = importlib.metadata.version("bitsandbytes")
        logger.info(f"bitsandbytes version: {version}")
        
        # Parse version
        major, minor, patch = 0, 0, 0
        try:
            parts = version.split('.')
            major = int(parts[0]) if len(parts) > 0 else 0
            minor = int(parts[1]) if len(parts) > 1 else 0
            patch = int(parts[2].split('+')[0]) if len(parts) > 2 else 0
        except:
            pass
        
        # Check if version >= 0.43.2 (supports device movement)
        supports_device_move = (major, minor, patch) >= (0, 43, 2)
        
        return {
            "available": True,
            "version": version,
            "supports_device_move": supports_device_move
        }
    except Exception as e:
        logger.warning(f"bitsandbytes not available: {e}")
        return {"available": False, "version": None, "supports_device_move": False}


TRL_AVAILABLE = check_trl_available()
BNB_INFO = check_bitsandbytes_version()


# ============================================================================
# Training Event Callbacks (for TypeScript backend communication)
# ============================================================================
class TrainingEventCallback(TrainerCallback):
    """
    Callback to output training events as JSON to stdout.
    These events are parsed by lora.ts to update the UI in real-time.
    """
    
    def __init__(self):
        super().__init__()
        self._last_logged_step = -1  # P0-4: 跟踪上次记录的 step 避免重复
    
    def on_log(self, args, state, control, logs=None, **kwargs):
        """Called when training metrics are logged."""
        if logs:
            # P0-FIX: 仅记录 step-level 的 loss，忽略 train_loss（epoch 平均值）
            # train_loss 是训练结束后的平均 loss，不应作为 step 指标记录
            # 否则会导致 Final Loss 异常跳跃（例如从 0.03 跳到 1.48）
            loss = logs.get('loss')
            if loss is None:
                # train_loss 是 epoch 结束时的平均 loss，跳过记录
                return
            # P0-4: 避免同一 step 重复输出
            if loss is not None and state.global_step > self._last_logged_step:
                self._last_logged_step = state.global_step
                event = {
                    "type": "metric",
                    "data": {
                        "step": state.global_step,
                        "loss": loss,
                        "lr": logs.get('learning_rate'),
                        "grad_norm": logs.get('grad_norm'),
                        "epoch": logs.get('epoch')
                    }
                }
                # Output to stdout for lora.ts to parse
                print(json.dumps(event), flush=True)
    
    def on_save(self, args, state, control, **kwargs):
        """Called when a checkpoint is saved."""
        checkpoint_path = f"checkpoint-{state.global_step}"
        event = {
            "type": "checkpoint",
            "data": {
                "path": checkpoint_path,
                "step": state.global_step,
                "epoch": state.epoch
            }
        }
        print(json.dumps(event), flush=True)
        logger.info(f"Checkpoint saved: {checkpoint_path}")


# ============================================================================
# Quantization Configuration
# ============================================================================
def get_quantization_config(quantization: str):
    """Get BitsAndBytes quantization config with compatibility fixes."""
    if not BNB_INFO["available"]:
        if quantization in ["4bit", "8bit"]:
            logger.warning("Quantization requested but bitsandbytes not available, using FP16")
        return None
    
    if quantization == "4bit":
        logger.info("Using 4-bit quantization (QLoRA)")
        # Note: llm_int8_enable_fp32_cpu_offload is for 8-bit only, NOT 4-bit
        return BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_use_double_quant=True,
        )
    elif quantization == "8bit":
        logger.info("Using 8-bit quantization")
        return BitsAndBytesConfig(
            load_in_8bit=True,
            llm_int8_enable_fp32_cpu_offload=True,
        )
    else:
        logger.info("No quantization, using FP16")
        return None


# ============================================================================
# Model Loading
# ============================================================================
def load_model_and_tokenizer(model_path: str, quantization: str):
    """
    Load model and tokenizer with proper quantization handling.
    Fixes the bitsandbytes device movement issue.
    """
    logger.info(f"Loading model from: {model_path}")
    
    # Load tokenizer
    tokenizer = AutoTokenizer.from_pretrained(
        model_path,
        trust_remote_code=True,
        use_fast=True,
    )
    
    # Set padding token
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
        tokenizer.pad_token_id = tokenizer.eos_token_id
    
    # Get quantization config
    quant_config = get_quantization_config(quantization)
    
    # Build model kwargs (following LeoLLM's successful approach)
    model_kwargs = {
        "trust_remote_code": True,
        "device_map": "auto",
    }
    
    if quant_config:
        model_kwargs["quantization_config"] = quant_config
        # For 4-bit: do NOT set torch_dtype, let bitsandbytes handle it
        # Setting torch_dtype with 4-bit can cause memory issues
    else:
        # Only set torch_dtype when NOT using quantization
        model_kwargs["torch_dtype"] = torch.float16
    
    # Load model
    model = AutoModelForCausalLM.from_pretrained(model_path, low_cpu_mem_usage=True, **model_kwargs)
    
    # Prepare for k-bit training if using quantization
    if quant_config:
        model = prepare_model_for_kbit_training(
            model,
            use_gradient_checkpointing=True
        )
    
    logger.info(f"Model loaded successfully")
    
    return model, tokenizer


# ============================================================================
# LoRA Setup
# ============================================================================
def setup_lora(model, lora_config: dict):
    """Setup LoRA adapter with extended target modules."""
    rank = lora_config.get('rank', 16)
    alpha = lora_config.get('alpha', 32)
    dropout = lora_config.get('dropout', 0.05)
    bias = lora_config.get('bias', 'none')  # 使用用户配置，默认 'none'
    
    # Extended target modules (like LeoLLM)
    default_targets = [
        "q_proj", "k_proj", "v_proj", "o_proj",
        "gate_proj", "up_proj", "down_proj"
    ]
    target_modules = lora_config.get('targetModules', default_targets)
    
    logger.info(f"Setting up LoRA: rank={rank}, alpha={alpha}, dropout={dropout}, bias={bias}, targets={target_modules}")
    
    peft_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=rank,
        lora_alpha=alpha,
        lora_dropout=dropout,
        target_modules=target_modules,
        bias=bias,  # 使用用户配置的 bias
    )
    
    model = get_peft_model(model, peft_config)
    model.print_trainable_parameters()
    
    return model


# ============================================================================
# Dataset Preparation - Messages Format
# ============================================================================
def prepare_dataset_messages(dataset_path: str) -> Dataset:
    """
    Prepare dataset in messages format for SFTTrainer.
    This enables automatic loss masking on assistant responses only.
    
    Supports 20+ common dataset formats via automatic detection:
    - Conversation: messages, sharegpt, openai_chatml, dialog_turns
    - Instruction: alpaca, dolly, wizardlm
    - Code: humaneval, mbpp, taco, code_completion, code_instruct
    - QA: qa_basic, qa_with_context, qa_choices
    - Generation: summarization, translation, rewriting
    - Special: chain_of_thought, sql_generation, math_solving, code_review
    - Fallback: text_only
    """
    from datasets import load_dataset as hf_load_dataset
    from format_registry import DatasetFormatRegistry
    
    logger.info(f"Loading dataset from: {dataset_path}")
    
    # Load dataset
    if dataset_path.endswith('.jsonl') or dataset_path.endswith('.json'):
        raw_dataset = hf_load_dataset('json', data_files=dataset_path, split='train')
    else:
        raw_dataset = hf_load_dataset(dataset_path, split='train')
    
    logger.info(f"Raw dataset loaded: {len(raw_dataset)} samples")
    
    # Initialize format registry
    registry = DatasetFormatRegistry(
        default_system_prompt="You are an expert Python programmer. Write clean, efficient, and correct code."
    )
    
    # Convert to messages format
    training_data = []
    skipped = 0
    format_stats: dict[str, int] = {}
    
    for i, sample in enumerate(raw_dataset):
        try:
            # Detect format
            format_name = registry.detect_format(sample)
            format_stats[format_name] = format_stats.get(format_name, 0) + 1
            
            if format_name == "unknown":
                skipped += 1
                if skipped <= 3:  # Log first few unknown samples
                    logger.warning(f"Unknown format for sample {i}, keys: {list(sample.keys())}")
                continue
            
            # Convert to messages
            messages = registry.convert_to_messages(sample, format_name)
            
            if not messages or len(messages) == 0:
                skipped += 1
                continue
            
            # Validate messages have assistant response
            has_assistant = any(m.get("role") == "assistant" for m in messages)
            if not has_assistant:
                skipped += 1
                continue
            
            # Validate messages have content
            assistant_content = ""
            for m in messages:
                if m.get("role") == "assistant":
                    assistant_content = m.get("content", "")
                    break
            
            if not assistant_content or not assistant_content.strip():
                skipped += 1
                continue
            
            training_data.append({"messages": messages})
            
        except Exception as e:
            logger.warning(f"Skipping sample {i}: {e}")
            skipped += 1
    
    # Log format statistics
    logger.info("=" * 60)
    logger.info("Dataset Format Statistics:")
    for fmt, count in sorted(format_stats.items(), key=lambda x: -x[1]):
        percentage = (count / len(raw_dataset)) * 100
        logger.info(f"  {fmt:20s}: {count:6d} ({percentage:5.1f}%)")
    logger.info("=" * 60)
    
    if skipped > 0:
        logger.warning(f"Skipped {skipped} invalid samples")
    
    if len(training_data) == 0:
        # 详细诊断信息
        logger.error("=" * 60)
        logger.error("DATASET ERROR: No valid training samples found!")
        logger.error(f"Raw dataset size: {len(raw_dataset)}")
        logger.error(f"Skipped samples: {skipped}")
        logger.error(f"Format detection results: {format_stats}")
        if len(raw_dataset) > 0:
            sample = raw_dataset[0]
            logger.error(f"Sample keys: {list(sample.keys())}")
            logger.error("Supported formats: " + ", ".join(registry.list_formats()))
        logger.error("=" * 60)
        raise ValueError(
            f"Dataset is empty after processing. "
            f"Raw samples: {len(raw_dataset)}, Skipped: {skipped}. "
            f"Format stats: {format_stats}. "
            f"Supported formats: {registry.list_formats()}"
        )
    
    logger.info(f"Prepared {len(training_data)} training samples (messages format)")
    
    return Dataset.from_list(training_data)


def prepare_dataset_tokenize(dataset_path: str, tokenizer, max_length: int = 512):
    """
    Fallback: Prepare dataset using traditional tokenization.
    Used when TRL is not available.
    """
    from datasets import load_dataset as hf_load_dataset
    
    logger.info(f"Loading dataset from: {dataset_path}")
    
    if dataset_path.endswith('.jsonl') or dataset_path.endswith('.json'):
        dataset = hf_load_dataset('json', data_files=dataset_path, split='train')
    else:
        dataset = hf_load_dataset(dataset_path, split='train')
    
    logger.info(f"Dataset loaded: {len(dataset)} samples")
    
    def tokenize_function(examples):
        if 'text' in examples:
            texts = examples['text']
        elif 'content' in examples:
            texts = examples['content']
        elif 'instruction' in examples:
            outputs = examples.get('output', examples.get('response', examples.get('reference', [''] * len(examples['instruction']))))
            texts = [
                f"### Instruction:\n{inst}\n\n### Response:\n{out}"
                for inst, out in zip(examples['instruction'], outputs)
            ]
        else:
            raise ValueError("Unsupported dataset format")
        
        tokenized = tokenizer(
            texts,
            truncation=True,
            max_length=max_length,
            padding="max_length",
        )
        tokenized["labels"] = tokenized["input_ids"].copy()
        return tokenized
    
    tokenized_dataset = dataset.map(
        tokenize_function,
        batched=True,
        remove_columns=dataset.column_names,
    )
    
    return tokenized_dataset


# ============================================================================
# Training with TRL SFTTrainer
# ============================================================================
def train_with_sft(model, tokenizer, dataset, eval_dataset, output_dir: str, training_config: dict):
    """
    Train using TRL SFTTrainer with messages format.
    This is the preferred method as it provides automatic loss masking.
    """
    from trl import SFTTrainer, SFTConfig
    
    logger.info("Training with TRL SFTTrainer (messages format)")
    
    # ==========================================================================
    # 基础训练参数
    # ==========================================================================
    num_epochs = training_config.get('epochs', 3)
    batch_size = training_config.get('batchSize', 1)
    grad_accum = training_config.get('gradientAccumulation', 8)
    learning_rate = float(training_config.get('lr', '2e-4'))
    max_length = training_config.get('maxLength', 512)
    weight_decay = training_config.get('weightDecay', 0.01)
    quantization = training_config.get('quantization', '4bit')
    
    # ==========================================================================
    # 核心训练参数 (新增)
    # ==========================================================================
    logging_steps = training_config.get('loggingSteps', 10)
    save_steps = training_config.get('saveSteps', 100)
    save_total_limit = training_config.get('saveTotalLimit', 3)
    max_grad_norm = training_config.get('gradientClipping', 1.0)
    
    # ==========================================================================
    # Warmup 配置 (新增) - 支持 ratio 或 steps 二选一
    # ==========================================================================
    warmup_type = training_config.get('warmupType', 'ratio')
    warmup_ratio = training_config.get('warmupRatio', 0.03)
    warmup_steps_cfg = training_config.get('warmupSteps', 0)
    
    # 根据 warmupType 决定使用 ratio 还是 steps
    if warmup_type == 'steps' and warmup_steps_cfg > 0:
        effective_warmup_ratio = 0  # 使用 steps 时禁用 ratio
        effective_warmup_steps = warmup_steps_cfg
    else:
        effective_warmup_ratio = warmup_ratio
        effective_warmup_steps = 0  # 使用 ratio 时禁用 steps
    
    # ==========================================================================
    # 验证配置 (新增)
    # ==========================================================================
    eval_strategy = training_config.get('evalStrategy', 'epoch')
    eval_steps_cfg = training_config.get('evalSteps', 200)
    
    # 如果没有验证集，强制设置为 "no"
    if eval_dataset is None:
        eval_strategy = 'no'
    
    # ==========================================================================
    # 高级训练选项 (新增)
    # ==========================================================================
    early_stopping_enabled = training_config.get('earlyStoppingEnabled', False)
    early_stopping_patience = training_config.get('earlyStoppingPatience', 3)
    early_stopping_threshold = training_config.get('earlyStoppingThreshold', 0.0)
    load_best_model_at_end = training_config.get('loadBestModelAtEnd', True)
    metric_for_best_model = training_config.get('metricForBestModel', 'loss')
    
    # ==========================================================================
    # 优化器与调度器
    # ==========================================================================
    optimizer = training_config.get('optimizer', 'paged_adamw_8bit')
    if quantization in ['4bit', '8bit'] and optimizer == 'adamw_torch':
        logger.info("Using paged_adamw_8bit for quantized model")
        optimizer = 'paged_adamw_8bit'
    
    precision = training_config.get('precision', 'none')
    use_fp16 = (precision == 'fp16') and quantization == 'none'
    use_bf16 = (precision == 'bf16') and quantization == 'none'
    
    scheduler = training_config.get('scheduler', 'cosine')

    # ==========================================================================
    # 日志输出完整配置信息
    # ==========================================================================
    logger.info(f"Training config: epochs={num_epochs}, batch_size={batch_size}, "
                f"grad_accum={grad_accum}, lr={learning_rate}, optimizer={optimizer}, "
                f"scheduler={scheduler}, precision={precision}")
    logger.info(f"Warmup: type={warmup_type}, ratio={effective_warmup_ratio}, steps={effective_warmup_steps}")
    logger.info(f"Logging: logging_steps={logging_steps}, save_steps={save_steps}, save_total_limit={save_total_limit}")
    logger.info(f"Eval: strategy={eval_strategy}, eval_steps={eval_steps_cfg if eval_strategy == 'steps' else 'N/A'}")
    logger.info(f"Advanced: max_grad_norm={max_grad_norm}, early_stopping={early_stopping_enabled}")
    
    # ==========================================================================
    # SFTConfig - 使用所有用户配置的参数
    # ==========================================================================
    sft_config = SFTConfig(
        output_dir=output_dir,
        num_train_epochs=num_epochs,
        per_device_train_batch_size=batch_size,
        gradient_accumulation_steps=grad_accum,
        learning_rate=learning_rate,
        weight_decay=weight_decay,
        lr_scheduler_type=scheduler,
        
        # Warmup 配置 - 根据用户选择使用 ratio 或 steps
        warmup_ratio=effective_warmup_ratio,
        warmup_steps=effective_warmup_steps,
        
        # Optimizer
        optim=optimizer,
        
        # Precision - 量化模型禁用以避免冲突
        fp16=use_fp16,
        bf16=use_bf16,
        
        # 内存优化
        gradient_checkpointing=True,
        max_grad_norm=max_grad_norm,  # 梯度裁剪
        
        # 日志和保存 - 使用用户配置
        logging_steps=logging_steps,
        save_steps=save_steps,
        save_total_limit=save_total_limit,
        report_to="none",
        
        # 验证配置 - 使用用户配置
        eval_strategy=eval_strategy,
        eval_steps=eval_steps_cfg if eval_strategy == 'steps' else None,
        
        # 最佳模型选择
        load_best_model_at_end=load_best_model_at_end if eval_strategy != 'no' else False,
        metric_for_best_model=metric_for_best_model if eval_strategy != 'no' else None,
        greater_is_better=False if metric_for_best_model == 'loss' else True,
        
        # SFT 特定参数
        max_length=max_length,
        packing=False,  # 不打包以保证准确性
    )
    
    # ==========================================================================
    # 创建回调列表
    # ==========================================================================
    callbacks = [TrainingEventCallback()]
    
    # 早停回调 (如果启用)
    if early_stopping_enabled and eval_strategy != 'no':
        from transformers import EarlyStoppingCallback
        early_stopping_callback = EarlyStoppingCallback(
            early_stopping_patience=early_stopping_patience,
            early_stopping_threshold=early_stopping_threshold,
        )
        callbacks.append(early_stopping_callback)
        logger.info(f"Early stopping enabled: patience={early_stopping_patience}, threshold={early_stopping_threshold}")
    
    # ==========================================================================
    trainer = SFTTrainer(
        model=model,
        args=sft_config,
        train_dataset=dataset,
        eval_dataset=eval_dataset,
        processing_class=tokenizer,
        callbacks=callbacks,
    )
    
    # ===== CHECKPOINT RESUME: 自动检测并从 checkpoint 恢复训练 =====
    resume_from_checkpoint = None
    if os.path.exists(output_dir):
        checkpoints = [
            d for d in os.listdir(output_dir) 
            if d.startswith('checkpoint-') and os.path.isdir(os.path.join(output_dir, d))
        ]
        if checkpoints:
            # 获取最新的 checkpoint（按 step 数排序）
            checkpoints.sort(key=lambda x: int(x.split('-')[1]), reverse=True)
            latest_checkpoint = os.path.join(output_dir, checkpoints[0])
            if os.path.exists(os.path.join(latest_checkpoint, 'trainer_state.json')):
                resume_from_checkpoint = latest_checkpoint
                logger.info(f"=== RESUMING FROM CHECKPOINT ===")
                logger.info(f"  Found checkpoint: {checkpoints[0]}")
                print(json.dumps({
                    "type": "log",
                    "level": "info",
                    "message": f"Resuming training from checkpoint: {checkpoints[0]}"
                }), flush=True)
    
    # Train (with optional resume)
    logger.info("Starting training...")
    if resume_from_checkpoint:
        train_result = trainer.train(resume_from_checkpoint=resume_from_checkpoint)
    else:
        train_result = trainer.train()
    
    # =========================================================================
    # P1: Collect runtime statistics for reproducibility
    # =========================================================================
    actual_steps = trainer.state.global_step
    
    # Get initial LR from optimizer (first param group)
    initial_lr = None
    try:
        if hasattr(trainer, 'optimizer') and trainer.optimizer:
            initial_lr = trainer.optimizer.param_groups[0].get('initial_lr') or trainer.optimizer.param_groups[0].get('lr')
    except:
        pass
    
    # Get peak GPU memory
    peak_gpu_memory_mb = None
    try:
        import torch
        if torch.cuda.is_available():
            peak_gpu_memory_mb = torch.cuda.max_memory_allocated() / (1024 * 1024)
    except:
        pass
    
    # Calculate throughput
    training_time_sec = train_result.metrics.get('train_runtime', 0)
    tokens_per_sec = None
    steps_per_sec = None
    if training_time_sec > 0:
        tokens_per_sec = (len(dataset) * max_length) / training_time_sec
        steps_per_sec = actual_steps / training_time_sec
    
    # Output training_summary event for backend parsing
    # P0-2/P0-3: 记录 config vs effective 的值以便报告显示
    summary_event = {
        "type": "training_summary",
        "data": {
            "planned_steps": trainer.state.max_steps,
            "actual_steps": actual_steps,
            "initial_lr": initial_lr,
            # P0-2: 记录配置 lr 和实际使用的 lr
            "config_lr": str(training_config.get('lr', '2e-4')),
            "effective_lr": learning_rate,  # 调整后的实际值
            # P0-3: 记录配置 scheduler 和实际使用的 scheduler
            "scheduler_config": training_config.get('scheduler', 'cosine'),
            "scheduler_effective": scheduler,  # 实际使用的
            "peak_gpu_memory_mb": peak_gpu_memory_mb,
            "tokens_per_second": tokens_per_sec,
            "steps_per_second": steps_per_sec,
            "final_loss": train_result.training_loss if hasattr(train_result, 'training_loss') else None,
            "epochs_completed": trainer.state.epoch,
        }
    }
    print(json.dumps(summary_event), flush=True)
    logger.info(f"Training summary: actual_steps={actual_steps}, peak_gpu_memory={peak_gpu_memory_mb:.0f}MB" if peak_gpu_memory_mb else f"Training summary: actual_steps={actual_steps}")
    
    # Save
    logger.info(f"Saving model to: {output_dir}")
    trainer.save_model(output_dir)
    tokenizer.save_pretrained(output_dir)
    
    logger.info("Training completed!")
    
    return actual_steps


def train_with_fallback(model, tokenizer, dataset, output_dir: str, training_config: dict):
    """
    Fallback training using standard Trainer when TRL is not available.
    """
    from transformers import TrainingArguments, Trainer, DataCollatorForSeq2Seq
    
    logger.info("Training with fallback Trainer (TRL not available)")
    
    num_epochs = training_config.get('epochs', 3)
    batch_size = training_config.get('batchSize', 1)
    grad_accum = training_config.get('gradientAccumulation', 8)
    learning_rate = float(training_config.get('lr', '2e-4'))
    save_steps = training_config.get('saveSteps', 100)
    quantization = training_config.get('quantization', '4bit')
    
    training_args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=num_epochs,
        per_device_train_batch_size=batch_size,
        gradient_accumulation_steps=grad_accum,
        learning_rate=learning_rate,
        warmup_ratio=0.03,
        logging_steps=1,
        save_steps=save_steps,
        save_total_limit=2,
        fp16=False if quantization in ['4bit', '8bit'] else True,
        optim="paged_adamw_8bit" if quantization in ['4bit', '8bit'] else "adamw_torch",
        report_to="none",
        remove_unused_columns=False,
        gradient_checkpointing=True,
    )
    
    data_collator = DataCollatorForSeq2Seq(
        tokenizer=tokenizer,
        padding=True,
        return_tensors="pt",
    )
    
    # Note: Small dataset auto-adjustment has been removed.
    # Training will use exactly what the user configured.

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
        data_collator=data_collator,
        callbacks=[TrainingEventCallback()],
    )
    
    logger.info("Starting training...")
    trainer.train()
    
    # Get actual steps from trainer
    actual_steps = trainer.state.global_step
    
    logger.info(f"Saving model to: {output_dir}")
    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)
    
    logger.info("Training completed!")
    
    return actual_steps


# ============================================================================
# Main Training Function
# ============================================================================
def train(config: dict):
    """Main training function with automatic method selection and comprehensive logging."""
    # =========================================================================
    # Initialize Experiment Logger
    # =========================================================================
    exp_logger = ExperimentLogger()
    run_id = config.get('runId', f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    seed = config.get('seed', 42)
    
    # Set random seeds for reproducibility
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    
    # Create experiment log
    experiment_log = exp_logger.create_log(run_id=run_id, seed=seed, config=config)
    logger.info(f"Experiment Log initialized: run_id={run_id}, seed={seed}")
    logger.info(f"Git commit: {experiment_log.git_commit or 'N/A'}")
    
    # Extract config
    model_path = config['modelPath']
    dataset_path = config['datasetPath']
    output_dir = config['outputDir']
    
    training_config = config.get('training', {})
    lora_config = config.get('lora', {})
    quantization = lora_config.get('quantization', '4bit')
    training_config['quantization'] = quantization
    
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Load model with proper quantization handling
    model, tokenizer = load_model_and_tokenizer(model_path, quantization)
    
    # Setup LoRA
    model = setup_lora(model, lora_config)
    
    # =========================================================================
    # Collect LoRA Statistics
    # =========================================================================
    experiment_log.lora_stats = exp_logger.collect_lora_stats(model)
    if experiment_log.lora_stats:
        logger.info(f"LoRA Stats: trainable={experiment_log.lora_stats.trainable_params:,} "
                    f"({experiment_log.lora_stats.trainable_percent:.4f}%)")
    
    # =========================================================================
    # Prepare Dataset and Train
    # =========================================================================
    training_start_time = time.time()
    total_steps = 0
    
    if TRL_AVAILABLE:
        # Use TRL SFTTrainer with messages format
        dataset = prepare_dataset_messages(dataset_path)
        
        # Load eval dataset if provided
        eval_dataset = None
        eval_dataset_path = config.get('evalDatasetPath')
        if eval_dataset_path:
            logger.info(f"Loading evaluation dataset from: {eval_dataset_path}")
            eval_dataset = prepare_dataset_messages(eval_dataset_path)
        
        # Collect dataset info
        experiment_log.dataset_info = exp_logger.collect_dataset_info(dataset_path, dataset, config)
        
        # =========================================================================
        # Collect Data Quality Statistics (P2: 详细数据质量分析)
        # =========================================================================
        try:
            from analyze_data_quality import DataQualityAnalyzer, output_data_quality_event
            max_length = training_config.get('maxLength', 512)
            
            logger.info("Analyzing data quality...")
            analyzer = DataQualityAnalyzer(tokenizer, max_length=max_length)
            data_quality_stats = analyzer.analyze(dataset, eval_dataset)
            
            # Output event for backend parsing
            output_data_quality_event(data_quality_stats)
            
            # Store in experiment log as JSON string
            experiment_log.data_quality_stats_json = analyzer.to_json(data_quality_stats)
            
            logger.info(f"Data quality score: {data_quality_stats.quality_score}/100")
        except Exception as e:
            logger.warning(f"Failed to collect data quality stats: {e}")
        
        # Clear cache before training
        torch.cuda.empty_cache()
        gc.collect()
        
        total_steps = train_with_sft(model, tokenizer, dataset, eval_dataset, output_dir, training_config)
    else:
        # Fallback to standard Trainer
        max_length = training_config.get('maxLength', 512)
        dataset = prepare_dataset_tokenize(dataset_path, tokenizer, max_length)
        
        # Collect dataset info even in fallback
        experiment_log.dataset_info = exp_logger.collect_dataset_info(dataset_path, dataset, config)
        
        total_steps = train_with_fallback(model, tokenizer, dataset, output_dir, training_config)
    
    # =========================================================================
    # Finalize Experiment Log
    # =========================================================================
    training_time = time.time() - training_start_time
    max_length = training_config.get('maxLength', 512)
    num_epochs = training_config.get('epochs', 3)
    total_tokens = len(dataset) * max_length * num_epochs
    
    experiment_log = exp_logger.finalize(
        experiment_log,
        total_steps=total_steps,
        total_tokens=total_tokens,
        training_time_seconds=training_time
    )
    
    # Log summary
    exp_logger.print_summary(experiment_log)
    
    # Save experiment log to file
    exp_log_path = os.path.join(output_dir, 'experiment_log.json')
    exp_logger.save_to_file(experiment_log, exp_log_path)
    
    # Output experiment log event for backend parsing
    output_experiment_log_event(experiment_log)
    
    return {
        "status": "complete", 
        "output_dir": output_dir,
        "experiment_log": asdict(experiment_log)
    }


# ============================================================================
# Entry Point
# ============================================================================
def main():
    parser = argparse.ArgumentParser(description="LLM Training with TRL SFTTrainer + QLoRA")
    parser.add_argument("--config", type=str, required=True, help="Path to config JSON file")
    args = parser.parse_args()
    
    # Load config
    with open(args.config, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    try:
        result = train(config)
        print(json.dumps(result))
    except Exception as e:
        logger.error(f"Training failed: {e}")
        import traceback
        traceback.print_exc()
        print(json.dumps({"status": "error", "error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
