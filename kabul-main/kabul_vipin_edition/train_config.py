from dataclasses import dataclass
import torch

@dataclass
class TrainingConfig:
    # Model Configuration
    base_model: str = "Salesforce/codet5-base"
    output_dir: str = "./fine_tuned_codet5_java_csharp" 
    max_length: int = 512
    
    # Training Hyperparameters
    learning_rate: float = 3e-5
    per_device_train_batch_size: int = 4
    per_device_eval_batch_size: int = 4
    gradient_accumulation_steps: int = 2
    num_train_epochs: int = 3
    
    # Optimizer
    weight_decay: float = 0.01
    warmup_steps: int = 500
    
    # Logging & Saving
    logging_steps: int = 10
    save_strategy: str = "epoch"
    save_total_limit: int = 2
    
    # Hardware
    fp16: bool = True  # Enable mixed precision for GPU
    no_cuda: bool = False
    
    # Data Paths (Fixed based on user requirement)
    java_train_path: str = "xlcost_data/data/Java-program-level/train.json"
    csharp_train_path: str = "xlcost_data/data/Csharp-program-level/train.json"
    java_valid_path: str = "xlcost_data/data/Java-program-level/valid.json"
    csharp_valid_path: str = "xlcost_data/data/Csharp-program-level/valid.json"

    @property
    def device(self):
        if self.no_cuda or not torch.cuda.is_available():
            return "cpu"
        return "cuda"
