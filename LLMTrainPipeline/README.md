# LLMTrainPipeline

An end-to-end LLM fine-tuning and evaluation pipeline with a modern web interface.

## Features

- 🎯 **Model Training**: LoRA/QLoRA fine-tuning with customizable parameters
- 📊 **Evaluation**: Comprehensive Pass@k evaluation with error analysis
- 📈 **Real-time Monitoring**: Live training metrics and progress tracking
- 📝 **Report Generation**: Detailed Markdown reports for training and evaluation
- 🔧 **Model Playground**: Interactive code generation testing
- 📁 **Dataset Management**: Support for multiple dataset formats

## Tech Stack

- **Frontend**: React + TypeScript + Vite + TailwindCSS
- **Backend**: Node.js + Express + TypeScript + Prisma
- **ML**: Python + PyTorch + Transformers + PEFT (LoRA)

## Prerequisites

- Node.js 18+
- Python 3.11+
- CUDA-capable GPU (for training/inference)

## Quick Start

### 1. Install Dependencies

```bash
# Frontend dependencies
npm install

# Backend dependencies
cd backend && npm install

# Python dependencies
cd backend/scripts
python3 -m pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Copy example environment file
cp .env.example .env.local

# Edit with your settings
# - GEMINI_API_KEY (optional, for AI features)
# - Model paths
# - Other configuration
```

### 3. Run the Application

**Option A: Using start script (Windows)**
```bash
./start.bat
```

**Option B: Manual start**
```bash
# Terminal 1: Start backend
cd backend && npm run dev

# Terminal 2: Start frontend
npm run dev
```

### 4. Access the App

Open http://localhost:4173 in your browser.

## Project Structure

```
LLMTrainPipeline/
├── App.tsx                 # Main React app
├── pages/                  # React pages
├── components/             # React components
├── backend/
│   ├── src/               # Backend source code
│   ├── scripts/           # Python ML scripts
│   │   ├── train.py       # Training script
│   │   ├── eval.py        # Evaluation script
│   │   └── infer.py       # Inference script
│   ├── storage/           # Data storage (not in git)
│   │   ├── models/        # Model weights
│   │   ├── adapters/      # LoRA adapters
│   │   ├── datasets/      # Training datasets
│   │   └── runs/          # Training runs
│   └── prisma/            # Database schema
└── package.json
```

## Storage Directories

The following directories are excluded from git (too large):

| Directory | Contents | Typical Size |
|-----------|----------|--------------|
| `backend/storage/models/` | Base model weights | 5-50 GB |
| `backend/storage/adapters/` | LoRA adapters | 10-500 MB each |
| `backend/storage/datasets/` | Training datasets | 100 MB - 10 GB |
| `backend/storage/runs/` | Training checkpoints | 1-50 GB |

## Configuration

Key configuration files:
- `.env.local` - Environment variables
- `backend/prisma/schema.prisma` - Database schema
- `vite.config.ts` - Frontend build config
- `backend/tsconfig.json` - Backend TypeScript config

## License

MIT License
