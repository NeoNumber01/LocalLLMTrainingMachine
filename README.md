# Code Translation and LLM Fine-tuning Project

> **Project Name**: CodeT5 Java→C# Code Translation System + LLM Training Pipeline  
> **Research Area**: Cross-lingual Code Translation Based on Large Language Models  
> **Last Updated**: 2026-01-29

---

## 📑 Table of Contents

1. [Project Overview](#-project-overview)
2. [Project Structure](#-project-structure)
3. [Requirements](#-requirements)
4. [kabul-main: Java→C# Translation System](#-kabul-main-javac-translation-system)
5. [LLMTrainPipeline: LLM Training Pipeline](#-llmtrainpipeline-llm-training-pipeline)
6. [Model Placement and Loading](#-model-placement-and-loading)
7. [Quick Start](#-quick-start)
8. [FAQ](#-faq)

---

## 🎯 Project Overview

This project contains two core subsystems:

### 1. kabul-main (CodeT5 Code Translation)
A Java → C# program-level code translation system based on **CodeT5** pre-trained model, including:
- Dataset alignment and preprocessing
- Model fine-tuning training
- Three-layer post-processing pipeline (Rule Cleaning → Formatting → Compiler-aided Self-healing)
- Multi-dimensional evaluation system (BLEU, CodeBLEU, Compilation Rate, Naming Conventions, etc.)

### 2. LLMTrainPipeline (LLM Training GUI)
An end-to-end LLM fine-tuning and evaluation pipeline with a modern web interface:
- **LoRA/QLoRA Fine-tuning**: Support for 4-bit/8-bit quantized training
- **Real-time Monitoring**: Training metrics visualization and progress tracking
- **Pass@k Evaluation**: Functional correctness testing for code generation
- **Report Generation**: Automatic Markdown report generation for training/evaluation
- **Model Playground**: Interactive code generation testing

---

## 📁 Project Structure

```
practical course/
├── README.md                    # This document
├── .gitignore                   # Git ignore rules
│
├── kabul-main/                  # Java→C# code translation system
│   ├── documentations/          # Project documentation
│   └── kabul_vipin_edition/     # ⭐ Core code
│       ├── train_model.py       # Main training script
│       ├── train_config.py      # Training hyperparameters config
│       ├── train_data.py        # Data loading and alignment
│       ├── align_datasets.py    # Test set data alignment
│       ├── evaluate_model.py    # Multi-dimensional evaluation
│       ├── post_process.py      # Post-processing pipeline
│       ├── generate_report.py   # Evaluation report generation
│       ├── verify_setup.py      # Environment verification
│       ├── codet5_base/         # 🔷 Base model (needs download)
│       ├── fine_tuned_codet5_java_csharp/  # Fine-tuned model
│       ├── xlcost_data/         # XLCoST dataset
│       └── metrics/             # Evaluation metrics modules
│
├── LLMTrainPipeline/            # LLM Training GUI pipeline
│   ├── App.tsx                  # React main app
│   ├── pages/                   # Frontend pages
│   ├── components/              # React components
│   ├── start.bat / start.sh     # ⭐ One-click start scripts
│   ├── stop.bat / stop.sh       # Stop scripts
│   ├── .env.example             # Environment variables template
│   ├── backend/                 # Backend service
│   │   ├── src/                 # TypeScript source code
│   │   ├── scripts/             # 🔷 Python ML scripts
│   │   │   ├── train.py         # Training script (TRL SFTTrainer)
│   │   │   ├── eval.py          # Evaluation script (Pass@k)
│   │   │   ├── infer.py         # Inference script
│   │   │   └── requirements.txt # Python dependencies
│   │   ├── storage/             # 🔷 Data storage (not in git)
│   │   │   ├── models/          # Base model weights
│   │   │   ├── adapters/        # LoRA adapters
│   │   │   ├── datasets/        # Training datasets
│   │   │   └── runs/            # Training run records
│   │   └── prisma/              # Database schema
│   └── docs/                    # Project documentation
│
├── thesis_ieee.tex              # Thesis LaTeX source
├── figures/                     # Thesis figures
└── documentations/              # Other documentation
```

---

## 💻 Requirements

### Hardware Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| **GPU** | NVIDIA RTX 3060 (8GB VRAM) | NVIDIA RTX 3080+ (16GB+ VRAM) |
| **RAM** | 16GB | 32GB+ |
| **Storage** | 50GB SSD | 100GB+ SSD |

### Software Requirements

| Software | Version | Purpose |
|----------|---------|---------|
| **Python** | 3.11+ | ML training and evaluation |
| **Node.js** | 18+ | Frontend/backend services |
| **CUDA** | 12.x | GPU acceleration |
| **.NET SDK** | 7.0/8.0 | C# compilation verification |
| **Git** | 2.x | Version control |

---

## 🔧 kabul-main: Java→C# Translation System

### System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     System Overall Architecture                  │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │ Data Prep    │───▶│ Model Train  │───▶│  Inference   │       │
│  │(Align/Preproc)│    │ (CodeT5 FT)  │    │ (Translate)  │       │
│  └──────────────┘    └──────────────┘    └──────────────┘       │
│         │                   │                   │               │
│         ▼                   ▼                   ▼               │
│  ┌──────────────────────────────────────────────────────┐       │
│  │               Post-Processing Pipeline               │       │
│  │  Layer 1: Rule Clean → Layer 2: Format → Layer 3: Self-Heal│ │
│  └──────────────────────────────────────────────────────┘       │
│                            │                                    │
│                            ▼                                    │
│  ┌──────────────────────────────────────────────────────┐       │
│  │               Multi-Dimensional Evaluation            │       │
│  │  BLEU │ CodeBLEU │ Compile Rate │ Exact Match │ Idioms │ Naming│
│  └──────────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────────┘
```

### Installation and Setup

```bash
# 1. Navigate to project directory
cd kabul-main/kabul_vipin_edition

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 3. Install dependencies
python3 -m pip install torch transformers datasets sacrebleu \
    tree-sitter tree-sitter-c-sharp pandas tqdm psutil

# 4. Verify environment
python3 verify_setup.py
```

### Workflow

#### Step 1: Data Alignment
```bash
python3 align_datasets.py
```
- **Input**: `xlcost_data/data/Java-program-level/test.json` & `Csharp.../test.json`
- **Output**: Aligned data in `xlcost_data/data/aligned/` directory

#### Step 2: Model Training
```bash
python3 train_model.py
```
- **Hyperparameter Config**: Edit `train_config.py`
- **Output Directory**: `fine_tuned_codet5_java_csharp/`
- **Training Report**: `fine_tuned_codet5_java_csharp/train_report.md`

#### Step 3: Model Evaluation
```bash
python3 evaluate_model.py
```
- **Output**:
  - `evaluation_summary.json` - Evaluation summary
  - `evaluation_results_multidim.csv` - Detailed per-sample results

#### Step 4: Generate Report
```bash
python3 generate_report.py
```
- **Output**: `research_paper_report.md` - Research report for paper publication

### Training Configuration (train_config.py)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `base_model` | `Salesforce/codet5-base` | Base model path |
| `output_dir` | `./fine_tuned_codet5_java_csharp` | Output directory |
| `learning_rate` | `3e-5` | Learning rate |
| `per_device_train_batch_size` | `4` | Single GPU batch size |
| `num_train_epochs` | `3` | Number of training epochs |
| `fp16` | `True` | Enable mixed precision |

---

## 🚀 LLMTrainPipeline: LLM Training Pipeline

### Tech Stack

| Layer | Technology | Description |
|-------|------------|-------------|
| **Frontend** | React + TypeScript + Vite + TailwindCSS | Modern UI |
| **Backend** | Node.js + Fastify + TypeScript + Prisma | REST API |
| **ML** | Python + PyTorch + Transformers + PEFT | LoRA Training |
| **Database** | SQLite | Lightweight storage |

### One-Click Start

**Windows:**
```bash
cd LLMTrainPipeline
./start.bat
```

**Linux/Mac:**
```bash
cd LLMTrainPipeline
chmod +x start.sh
./start.sh
```

Startup Mode Options:
1. **Development Mode** - Hot reload, suitable for debugging
2. **Stable Mode** - No hot reload, suitable for long training/evaluation
3. **Backend Only** - Start only backend service
4. **Frontend Only** - Start only frontend service

### Manual Start

```bash
# Terminal 1: Backend service
cd LLMTrainPipeline/backend
npm install
npm run db:generate
npm run db:push
npm run dev

# Terminal 2: Frontend service
cd LLMTrainPipeline
npm install
npm run dev
```

### Access URLs

| Service | URL |
|---------|-----|
| **Frontend UI** | http://localhost:4173 |
| **Backend API** | http://localhost:3001 |
| **API Docs** | http://localhost:3001/docs |

### Python Dependencies Installation

```bash
cd LLMTrainPipeline/backend/scripts
python3 -m pip install -r requirements.txt
```

### Main Feature Modules

#### 1. Training Module (train.py)
- Supports TRL SFTTrainer + QLoRA
- Automatic data format detection (20+ formats)
- Real-time training event output
- Automatic checkpoint saving

#### 2. Evaluation Module (eval.py)
- Pass@k evaluation (k=1,5,10)
- Error classification statistics
- Execution time analysis
- Code quality assessment

#### 3. Inference Module (infer.py)
- Chat Template support
- Streaming output
- Batch inference

---

## 📦 Model Placement and Loading

### kabul-main Model Configuration

#### Base Model Location
```
kabul-main/kabul_vipin_edition/codet5_base/
├── pytorch_model.bin      # ~890MB model weights
├── config.json            # Model configuration
├── tokenizer_config.json  # Tokenizer configuration
├── vocab.json             # Vocabulary
└── merges.txt             # BPE merge rules
```

#### Download Base Model
```python
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

# Method 1: Automatic download from HuggingFace
model = AutoModelForSeq2SeqLM.from_pretrained("Salesforce/codet5-base")
tokenizer = AutoTokenizer.from_pretrained("Salesforce/codet5-base")

# Save to local
model.save_pretrained("./codet5_base")
tokenizer.save_pretrained("./codet5_base")

# Method 2: Use local path
model = AutoModelForSeq2SeqLM.from_pretrained("./codet5_base")
```

#### Fine-tuned Model Location
```
kabul-main/kabul_vipin_edition/fine_tuned_codet5_java_csharp/
├── final_model/           # Final model weights
│   ├── model.safetensors  # ~890MB
│   ├── config.json
│   └── tokenizer files...
├── checkpoint-*/          # Training checkpoints
└── train_report.md        # Training report
```

#### Load Fine-tuned Model
```python
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

model_path = "./fine_tuned_codet5_java_csharp/final_model"
model = AutoModelForSeq2SeqLM.from_pretrained(model_path)
tokenizer = AutoTokenizer.from_pretrained(model_path)

# Use model for translation
java_code = "public static void main(String[] args) { ... }"
inputs = tokenizer(f"translate Java to C#: {java_code}", return_tensors="pt")
outputs = model.generate(**inputs, max_length=512)
csharp_code = tokenizer.decode(outputs[0], skip_special_tokens=True)
```

---

### LLMTrainPipeline Model Configuration

#### Storage Directory Structure
```
LLMTrainPipeline/backend/storage/
├── models/                # Base model weights
│   ├── Qwen2.5-3B/        # Example: Qwen model
│   ├── CodeLlama-7B/      # Example: CodeLlama model
│   └── ...
├── adapters/              # LoRA adapters
│   ├── my-lora-adapter/   # Trained adapter
│   └── ...
├── datasets/              # Training datasets
│   ├── my-dataset.json    # Custom dataset
│   └── ...
└── runs/                  # Training run records
    ├── run-001/           # Contains checkpoints and logs
    └── ...
```

#### Model Download and Placement

**Method 1: Using HuggingFace CLI**
```bash
# Install huggingface-hub
pip install huggingface-hub

# Download model to specified directory
huggingface-cli download Qwen/Qwen2.5-3B-Instruct \
    --local-dir LLMTrainPipeline/backend/storage/models/Qwen2.5-3B
```

**Method 2: Using Python**
```python
from transformers import AutoModelForCausalLM, AutoTokenizer

model_name = "Qwen/Qwen2.5-3B-Instruct"
save_path = "./backend/storage/models/Qwen2.5-3B"

model = AutoModelForCausalLM.from_pretrained(model_name)
tokenizer = AutoTokenizer.from_pretrained(model_name)

model.save_pretrained(save_path)
tokenizer.save_pretrained(save_path)
```

#### Loading Model in GUI

1. Start LLMTrainPipeline (`./start.bat`)
2. Add model path in the **Models** page of the web interface
3. Or specify model path when creating a new Run in the **Training** page

#### Loading Trained Adapters

```python
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

# Load base model
base_model = AutoModelForCausalLM.from_pretrained(
    "./backend/storage/models/Qwen2.5-3B",
    device_map="auto",
    load_in_4bit=True  # Optional: 4-bit quantization
)
tokenizer = AutoTokenizer.from_pretrained("./backend/storage/models/Qwen2.5-3B")

# Load LoRA adapter
model = PeftModel.from_pretrained(
    base_model,
    "./backend/storage/adapters/my-lora-adapter"
)

# Inference
inputs = tokenizer("Your prompt here", return_tensors="pt")
outputs = model.generate(**inputs, max_new_tokens=256)
print(tokenizer.decode(outputs[0]))
```

---

## ⚡ Quick Start

### kabul-main Quick Training

```bash
cd kabul-main/kabul_vipin_edition

# 1. Install dependencies
python3 -m pip install torch transformers datasets sacrebleu pandas tqdm

# 2. Align data
python3 align_datasets.py

# 3. Train model (~1-2 hours/epoch, depends on GPU)
python3 train_model.py

# 4. Evaluate model
python3 evaluate_model.py

# 5. View report
cat evaluation_summary.json
```

### LLMTrainPipeline Quick Start

```bash
cd LLMTrainPipeline

# 1. One-click start (Windows)
./start.bat

# 2. Open in browser
# http://localhost:4173

# 3. In the GUI:
#    - Add model path
#    - Upload dataset
#    - Configure training parameters
#    - Start training!
```

---

## ❓ FAQ

### Q1: Compilation Rate is 0% or N/A
**Cause**: .NET SDK is not installed or not in PATH  
**Solution**: Install .NET SDK 7.0/8.0, verify with `dotnet --version`

### Q2: CUDA/GPU Not Being Used
**Cause**: PyTorch was installed without CUDA support  
**Solution**:
```bash
pip3 uninstall torch
pip3 install torch --index-url https://download.pytorch.org/whl/cu121
```

### Q3: Out of Memory (OOM)
**Solutions**:
- Reduce `per_device_train_batch_size`
- Enable gradient accumulation (`gradient_accumulation_steps`)
- Use 4-bit quantized training (`load_in_4bit=True`)

### Q4: Dataset Not Found
**Check directory structure**:
```
xlcost_data/
  data/
    Java-program-level/train.json
    Csharp-program-level/train.json
    aligned/  ← Generated by running align_datasets.py
```

### Q5: LLMTrainPipeline Backend Cannot Start
**Troubleshooting steps**:
1. Ensure Node.js 18+ is installed
2. Run `cd backend && npm install`
3. Run `npm run db:generate && npm run db:push`
4. Check if port 3001 is occupied

---

## 📄 License

MIT License

---

## 📚 References

1. Wang et al., "CodeT5: Identifier-aware Unified Pre-trained Encoder-Decoder Models for Code Understanding and Generation", EMNLP 2021
2. Zhu et al., "XLCoST: A Benchmark Dataset for Cross-lingual Code Intelligence", arXiv 2022
3. Ren et al., "CodeBLEU: a Method for Automatic Evaluation of Code Synthesis", arXiv 2020

---

*Document Last Updated: 2026-01-29*
