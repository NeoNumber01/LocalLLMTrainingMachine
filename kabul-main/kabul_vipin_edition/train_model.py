from transformers import (
    AutoTokenizer, 
    AutoModelForSeq2SeqLM, 
    Seq2SeqTrainingArguments, 
    Seq2SeqTrainer,
    DataCollatorForSeq2Seq
)
from train_config import TrainingConfig
from train_data import JavaCSharpDataset
from train_report import TrainingReporter
import os
import torch

def main():
    # 1. Load Configuration
    import torch
    print(f"CUDA Available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"Device: {torch.cuda.get_device_name(0)}")
        
    config = TrainingConfig()
    print(f"Initializing training with device: {config.device}")
    
    # 2. Setup Reporting
    reporter = TrainingReporter(config.output_dir, config)
    
    # 3. Load Tokenizer & Model
    print(f"Loading model: {config.base_model}")
    tokenizer = AutoTokenizer.from_pretrained(config.base_model)
    model = AutoModelForSeq2SeqLM.from_pretrained(config.base_model)
    
    # Move model to device (TrainingArguments handles this usually, but good for check)
    # model.to(config.device) 

    # 4. Load & Align Data
    print("Preparing datasets...")
    data_handler = JavaCSharpDataset(config, tokenizer)
    train_dataset = data_handler.get_train_dataset()
    valid_dataset = data_handler.get_valid_dataset()
    
    # Log data sizes
    print(f"Training samples: {len(train_dataset)}")
    print(f"Validation samples: {len(valid_dataset)}")
    
    # Record model info for report
    reporter.set_model_info(model)
    
    # Record data stats (note: dedup counts are logged by align_data)
    reporter.set_data_stats(
        train_samples=len(train_dataset),
        valid_samples=len(valid_dataset)
    )
    
    # 5. Training Arguments
    training_args = Seq2SeqTrainingArguments(
        output_dir=config.output_dir,
        num_train_epochs=config.num_train_epochs,
        per_device_train_batch_size=config.per_device_train_batch_size,
        per_device_eval_batch_size=config.per_device_eval_batch_size,
        gradient_accumulation_steps=config.gradient_accumulation_steps,
        learning_rate=config.learning_rate,
        weight_decay=config.weight_decay,
        warmup_steps=config.warmup_steps,
        logging_steps=config.logging_steps,
        save_strategy=config.save_strategy,
        save_total_limit=config.save_total_limit,
        eval_strategy="epoch",
        fp16=config.fp16 and torch.cuda.is_available(),
        predict_with_generate=True,
        report_to=["none"],  # We use our own reporter
        # Explicitly force GPU usage
        use_cpu=False,
        dataloader_pin_memory=False,  # Avoid the pin_memory warning on CPU fallback
    )
    
    print(f"Training device: {training_args.device}")


    # 6. Initialize Trainer
    trainer = Seq2SeqTrainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=valid_dataset,
        tokenizer=tokenizer,
        data_collator=DataCollatorForSeq2Seq(tokenizer, model=model),
    )
    
    # Custom Callback for our Reporter
    from transformers import TrainerCallback
    
    class ReporterCallback(TrainerCallback):
        def on_log(self, args, state, control, logs=None, **kwargs):
            if logs and "loss" in logs:
                reporter.log_step(state.global_step, logs["loss"], logs.get("learning_rate", 0))

        def on_evaluate(self, args, state, control, metrics=None, **kwargs):
            if metrics and "eval_loss" in metrics:
                reporter.on_epoch_end(
                    epoch=int(state.epoch) if state.epoch else 0,
                    eval_loss=metrics["eval_loss"],
                    metrics=metrics
                )

    trainer.add_callback(ReporterCallback)

    # 7. Start Training
    print("Starting training...")
    trainer.train()
    
    # 8. Save Final Model
    print("Saving final model...")
    trainer.save_model(os.path.join(config.output_dir, "final_model"))
    tokenizer.save_pretrained(os.path.join(config.output_dir, "final_model"))
    
    # 9. Generate Report
    reporter.generate_report()
    print("Training finished successfully!")

if __name__ == "__main__":
    main()
