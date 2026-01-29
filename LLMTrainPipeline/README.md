# LLMTrainPipeline

> **End-to-end LLM Fine-tuning and Evaluation Platform**  
> Modern web interface for LoRA/QLoRA training with real-time monitoring

---

## 🎯 Features

- **🎓 Model Training**: LoRA/QLoRA fine-tuning with customizable parameters
- **📊 Evaluation**: Comprehensive Pass@k evaluation with error analysis
- **📈 Real-time Monitoring**: Live training metrics and progress tracking
- **📝 Report Generation**: Detailed Markdown reports for training and evaluation
- **🔧 Model Playground**: Interactive code generation testing
- **📁 Dataset Management**: Support for 20+ dataset formats

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | React + TypeScript + Vite + TailwindCSS |
| **Backend** | Node.js + Fastify + TypeScript + Prisma |
| **ML** | Python + PyTorch + Transformers + PEFT + TRL |
| **Database** | SQLite |

---

## 📁 Project Structure

```
LLMTrainPipeline/
├── Frontend
│   ├── App.tsx              # React main app
│   ├── pages/               # Page components
│   ├── components/          # UI components
│   └── index.html           # Entry HTML
│
├── Backend (backend/)
│   ├── src/                 # TypeScript source
│   │   ├── routes/          # API routes
│   │   ├── services/        # Business logic
│   │   ├── providers/       # Provider implementations
│   │   └── config/          # Configuration system
│   ├── scripts/             # Python ML scripts
│   │   ├── train.py         # Training (TRL SFTTrainer)
│   │   ├── eval.py          # Evaluation (Pass@k)
│   │   ├── infer.py         # Inference
│   │   └── requirements.txt # Python dependencies
│   ├── prisma/              # Database schema
│   └── storage/             # Data storage (not in git)
│       ├── models/          # Base model weights
│       ├── adapters/        # LoRA adapters
│       ├── datasets/        # Training datasets
│       └── runs/            # Training run records
│
├── start.bat / start.sh     # One-click start scripts
├── stop.bat / stop.sh       # Stop scripts
└── .env.example             # Environment template
```

---

## 💻 Requirements

### Hardware
| Component | Minimum | Recommended |
|-----------|---------|-------------|
| GPU | RTX 3060 (8GB VRAM) | RTX 3080+ (16GB VRAM) |
| RAM | 16GB | 32GB+ |
| Storage | 50GB SSD | 100GB+ SSD |

### Software
- **Node.js**: 18+
- **Python**: 3.11+
- **CUDA**: 12.x

---

## 🚀 Quick Start

### Option 1: One-Click Start (Recommended)

**Windows:**
```bash
./start.bat
```

**Linux/Mac:**
```bash
chmod +x start.sh
./start.sh
```

Select startup mode:
1. **Development Mode** - Hot reload for debugging
2. **Stable Mode** - No hot reload for long training tasks
3. **Backend Only** - API server only
4. **Frontend Only** - UI only

### Option 2: Manual Start

```bash
# Terminal 1: Backend
cd backend
npm install
npm run db:generate
npm run db:push
npm run dev

# Terminal 2: Frontend
npm install
npm run dev
```

### Install Python Dependencies

```bash
cd backend/scripts
python3 -m pip install -r requirements.txt
```

---

## 🌐 Access URLs

| Service | URL |
|---------|-----|
| **Frontend UI** | http://localhost:4173 |
| **Backend API** | http://localhost:3001 |
| **Swagger Docs** | http://localhost:3001/docs |
| **Health Check** | http://localhost:3001/health |

---

## 📦 Model Setup

### Storage Directory Structure

```
backend/storage/
├── models/          # Place base models here
│   └── Qwen2.5-3B/  # Example model
├── adapters/        # LoRA adapters (auto-created)
├── datasets/        # Training datasets
└── runs/            # Training runs (auto-created)
```

### Download Models

**Using HuggingFace CLI:**
```bash
pip install huggingface-hub

huggingface-cli download Qwen/Qwen2.5-3B-Instruct \
    --local-dir backend/storage/models/Qwen2.5-3B
```

**Using Python:**
```python
from transformers import AutoModelForCausalLM, AutoTokenizer

model = AutoModelForCausalLM.from_pretrained("Qwen/Qwen2.5-3B-Instruct")
tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-3B-Instruct")

model.save_pretrained("./backend/storage/models/Qwen2.5-3B")
tokenizer.save_pretrained("./backend/storage/models/Qwen2.5-3B")
```

---

## 📊 Training Workflow

### 1. Add Model
- Go to **Models** page in UI
- Add path to your model in `storage/models/`

### 2. Upload Dataset
- Go to **Datasets** page
- Upload JSON/JSONL dataset files
- Supports 20+ formats (auto-detected)

### 3. Create Training Run
- Go to **Training** page → **New Run**
- Configure: model, dataset, LoRA params, epochs, etc.
- Click **Start**

### 4. Monitor Progress
- Real-time loss curves
- Step-by-step logging
- Automatic checkpointing

### 5. Evaluate
- Go to **Evaluation** page
- Select trained adapter
- Run Pass@k evaluation

### 6. Generate Reports
- Automatic training reports in Markdown
- Evaluation reports with error analysis

---

## ⚙️ Configuration

### Environment Variables (`.env.local`)

```bash
# Copy from template
cp .env.example .env.local

# Edit with your settings
GEMINI_API_KEY=your_api_key_here  # Optional, for AI features
```

### Backend Config (`src/config/defaults.yaml`)

```yaml
providers:
  compute: "local_single"      # local_single | local_multi_fsdp
  trainer: "lora"              # lora | full_finetune
  eval: "code_passk"           # code_passk
  artifactStore: "filesystem"  # filesystem | s3
```

---

## 🐍 Python Scripts

### train.py
- TRL SFTTrainer with QLoRA
- Automatic dataset format detection
- Real-time event output for UI
- Checkpoint saving

### eval.py
- Pass@k evaluation (k=1,5,10)
- Error classification (syntax, runtime, timeout)
- Execution time analysis
- Code quality metrics

### infer.py
- Chat template support
- Streaming output
- Batch inference

---

## 🔄 Loading Trained Adapters

```python
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

# Load base model with quantization
base_model = AutoModelForCausalLM.from_pretrained(
    "./backend/storage/models/Qwen2.5-3B",
    device_map="auto",
    load_in_4bit=True
)
tokenizer = AutoTokenizer.from_pretrained(
    "./backend/storage/models/Qwen2.5-3B"
)

# Load LoRA adapter
model = PeftModel.from_pretrained(
    base_model,
    "./backend/storage/adapters/my-adapter"
)

# Generate
inputs = tokenizer("Write a function to...", return_tensors="pt")
outputs = model.generate(**inputs, max_new_tokens=256)
print(tokenizer.decode(outputs[0]))
```

---

## ❓ Troubleshooting

### Backend won't start
```bash
cd backend
npm install
npm run db:generate
npm run db:push
```

### Port 3001 occupied
```bash
# Windows
netstat -ano | findstr :3001
taskkill /PID <pid> /F

# Linux/Mac
lsof -i :3001
kill -9 <pid>
```

### CUDA not detected
```bash
pip uninstall torch
pip install torch --index-url https://download.pytorch.org/whl/cu121
```

### Out of Memory (OOM)
- Reduce batch size in training config
- Enable gradient accumulation
- Use 4-bit quantization (`load_in_4bit=True`)

---

## 📄 License

MIT License
