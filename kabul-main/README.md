# KABUL: Java → C# Code Translation System

> **CodeT5-based Cross-lingual Code Translation System**  
> Fine-tuned on XLCoST dataset for program-level Java to C# translation

---

## 🎯 Overview

KABUL is a neural machine translation system that automatically converts Java source code to semantically equivalent C# code. Built on the **CodeT5** pre-trained model with a comprehensive post-processing pipeline and multi-dimensional evaluation framework.

### Key Features
- **Fine-tuned CodeT5 Model**: Optimized for Java→C# translation task
- **Three-layer Post-processing**: Rule cleaning → Formatting → Compiler-aided self-healing
- **Multi-dimensional Evaluation**: BLEU, CodeBLEU, Compilation Rate, Naming Conventions
- **XLCoST Dataset**: Aligned training data from cross-lingual code benchmark

---

## 📁 Project Structure

```
kabul_vipin_edition/
├── Core Scripts
│   ├── train_model.py        # Main training script
│   ├── train_config.py       # Training hyperparameters
│   ├── train_data.py         # Data loading & alignment
│   ├── align_datasets.py     # Test set data alignment
│   ├── evaluate_model.py     # Multi-dimensional evaluation
│   ├── post_process.py       # Post-processing pipeline
│   ├── generate_report.py    # Report generation
│   └── verify_setup.py       # Environment verification
│
├── Metrics (metrics/)
│   ├── codebleu_eval.py      # CodeBLEU calculation
│   ├── compilation_eval.py   # Compilation rate eval
│   ├── exact_match_eval.py   # Exact match rate
│   ├── idiom_eval.py         # C# idiom density
│   ├── naming_eval.py        # Naming convention score
│   └── native_codebleu/      # Native tree-sitter impl
│
├── Datasets (xlcost_data/)
│   └── data/
│       ├── Java-program-level/    # Java source data
│       ├── Csharp-program-level/  # C# target data
│       └── aligned/               # Aligned pairs
│
├── Models
│   ├── codet5_base/                      # Base model (~890MB)
│   └── fine_tuned_codet5_java_csharp/    # Fine-tuned model
│
└── Outputs
    ├── evaluation_summary.json           # Eval summary
    ├── evaluation_results_multidim.csv   # Detailed results
    └── research_paper_report.md          # Research report
```

---

## 💻 Requirements

### Hardware
| Component | Minimum | Recommended |
|-----------|---------|-------------|
| GPU | RTX 3060 (8GB VRAM) | RTX 3080+ (16GB VRAM) |
| RAM | 16GB | 32GB |
| Storage | 10GB | 50GB |

### Software
- **Python**: 3.10+ (3.11 recommended)
- **CUDA**: 11.8 or 12.x
- **.NET SDK**: 7.0/8.0 (for C# compilation verification)

---

## 🚀 Quick Start

### 1. Environment Setup

```bash
cd kabul-main/kabul_vipin_edition

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Install dependencies
python3 -m pip install torch transformers datasets sacrebleu \
    tree-sitter tree-sitter-c-sharp pandas tqdm psutil

# Verify setup
python3 verify_setup.py
```

### 2. Data Alignment

```bash
python3 align_datasets.py
```

**Input**: Raw Java/C# test data from `xlcost_data/data/`  
**Output**: Aligned pairs in `xlcost_data/data/aligned/`

### 3. Model Training

```bash
python3 train_model.py
```

**Duration**: ~1-2 hours per epoch (GPU dependent)  
**Output**: `fine_tuned_codet5_java_csharp/final_model/`

### 4. Model Evaluation

```bash
python3 evaluate_model.py
```

**Output**:
- `evaluation_summary.json` - Aggregate metrics
- `evaluation_results_multidim.csv` - Per-sample results

### 5. Generate Report

```bash
python3 generate_report.py
```

**Output**: `research_paper_report.md`

---

## ⚙️ Configuration

Edit `train_config.py` to customize training:

```python
@dataclass
class TrainingConfig:
    base_model: str = "Salesforce/codet5-base"
    output_dir: str = "./fine_tuned_codet5_java_csharp"
    
    # Hyperparameters
    learning_rate: float = 3e-5
    per_device_train_batch_size: int = 4
    gradient_accumulation_steps: int = 2
    num_train_epochs: int = 3
    
    # Hardware
    fp16: bool = True  # Mixed precision
```

---

## 📊 Evaluation Metrics

| Dimension | Metric | Description |
|-----------|--------|-------------|
| **Semantics** | BLEU | N-gram text similarity |
| **Semantics** | CodeBLEU | AST + DataFlow matching |
| **Executable** | Compilation Rate | .NET build success rate |
| **Quality** | Naming Score | PascalCase compliance |
| **Quality** | C# Idioms | LINQ/var/foreach usage |

---

## 🔧 Post-Processing Pipeline

```
Layer 1: Rule Cleaning
├── Remove markdown code blocks
├── Primitive type mapping (boolean→bool)
├── String method mapping (.length()→.Length)
├── Collection mapping (ArrayList→List)
└── I/O mapping (System.out→Console)

Layer 2: Syntax Formatting
└── dotnet format for code style

Layer 3: Compiler-Aided Self-Healing
├── Parse compilation errors (CS1002, CS0103...)
├── Apply heuristic repairs
└── Iterate up to 3 rounds
```

---

## 📦 Model Loading

### Download Base Model
```python
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

model = AutoModelForSeq2SeqLM.from_pretrained("Salesforce/codet5-base")
tokenizer = AutoTokenizer.from_pretrained("Salesforce/codet5-base")
model.save_pretrained("./codet5_base")
tokenizer.save_pretrained("./codet5_base")
```

### Load Fine-tuned Model
```python
model_path = "./fine_tuned_codet5_java_csharp/final_model"
model = AutoModelForSeq2SeqLM.from_pretrained(model_path)
tokenizer = AutoTokenizer.from_pretrained(model_path)

# Translate Java to C#
java_code = "public static void main(String[] args) { ... }"
inputs = tokenizer(f"translate Java to C#: {java_code}", return_tensors="pt")
outputs = model.generate(**inputs, max_length=512)
csharp_code = tokenizer.decode(outputs[0], skip_special_tokens=True)
```

---

## 📚 References

1. Wang et al., "CodeT5: Identifier-aware Unified Pre-trained Encoder-Decoder Models", EMNLP 2021
2. Zhu et al., "XLCoST: A Benchmark Dataset for Cross-lingual Code Intelligence", arXiv 2022
3. Ren et al., "CodeBLEU: a Method for Automatic Evaluation of Code Synthesis", arXiv 2020

---

## 📄 License

MIT License
