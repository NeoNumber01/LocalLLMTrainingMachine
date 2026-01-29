# LLMTrainPipeline User Guide

Welcome to **LLMTrainPipeline** (Nexus AI), your end-to-end system for fine-tuning and evaluating Large Language Models (LLMs). This guide will help you get started with installing the system, managing your models and datasets, and executing training and evaluation workflows.

---

## 1. Installation & Setup

### Prerequisites
Before you begin, ensure your system meets the following requirements:
- **OS**: Windows, Linux, or macOS
- **Node.js**: Version 18 or higher
- **Python**: Version 3.11 or higher
- **GPU**: NVIDIA GPU with CUDA support (recommended for training)

### Initial Setup
1. **Clone the repository** (if you haven't already).
2. **Install Dependencies**:
   While the launcher script handles most of this, you can manually install dependencies if needed:
   ```bash
   # Install frontend dependencies
   npm install

   # Install backend dependencies
   cd backend
   npm install

   # Install Python requirements
   cd scripts
   pip install -r requirements.txt
   ```

---

## 2. Launching the Application

We provide easy-to-use launcher scripts for all platforms.

### Windows
Double-click `start.bat` or run it from the command line:
```cmd
./start.bat
```

### Linux / macOS
Run the shell script:
```bash
./start.sh
```

### Startup Modes
You will be prompted to choose a mode:
1. **Development Mode**: Hot-reload enabled for both frontend and backend. Best for developers modifying the codebase.
2. **Stable Mode (Recommended)**: Backend runs without hot-reload. **Use this for Training and Evaluation** to prevent interruptions if files change.
3. **Backend/Frontend Only**: Start only specific services.

Once started, the application will automatically open in your default browser at `http://localhost:5173` (or similar).

---

## 3. Managing Resources

Before you can train or evaluate, you need to register your models and datasets.

### Models

You have two ways to add models to the system:

#### Option A: Auto-Scan (Recommended)
1.  **Locate the Storage Folder**: Find the `storage/models` directory in the project root.
    - If it doesn't exist, create it: `mkdir -p storage/models`.
2.  **Place Your Model**: Move your HuggingFace model folder here.
    - Example structure: `storage/models/Llama-2-7b-hf/` (should contain `config.json`, `pytorch_model.bin` etc.)
3.  **Scan**:
    - Go to the **Models** page.
    - The "Models Scanner" panel on the left automatically watches this folder.
    - Click **Scan Now** if your model doesn't appear immediately.

#### Option B: Manual Import
1.  Go to the **Models** page.
2.  Click **Import**.
3.  Enter the **absolute path** to your model folder on your disk.

### Datasets

#### Option A: Auto-Scan
1.  **Locate the Storage Folder**: Find `storage/train_datasets` (for training) or `storage/eval_datasets` (for evaluation).
    - Note: You can also just use `storage/datasets` and let the system detect the type.
2.  **Place Your File**: Copy your dataset file (JSONL, JSON, or Parquet) into this folder.
    - Example: `storage/train_datasets/alpaca_data.jsonl`
3.  **Scan**:
    - Go to the **Datasets** page.
    - Use the "Datasets Scanner" panel on the left to scan for changes.

#### Option B: UI Import
1.  Go to the **Datasets** page.
2.  Click **Import File** to select a single file, or **Import Folder** to scan a directory.
3.  **Select Type**: The system will try to auto-detect if it's a "Train" or "Eval" dataset based on the filename (e.g., if it contains "eval" or "test"), but you can verify this after import.

#### Supported Data Formats
The system supports most common LLM formats including:
- **Alpaca**: `{"instruction": "...", "input": "...", "output": "..."}`
- **ShareGPT**: `{"conversations": [{"from": "human", "value": "..."}]}`
- **Messages**: `{"messages": [{"role": "user", "content": "..."}]}`


---

## 4. Fine-Tuning Your Model (Training)

To create a new fine-tuning task:

1. Go to **New Run** in the sidebar.
2. **Step 1: Select Model**: Choose your base model from the list.
3. **Step 2: Select Dataset**: Choose your training dataset. You can also optionally select a validation dataset.
4. **Step 3: Configuration**:
   - **Basic Parameters**:
     - **Learning Rate**: Controls how fast the model learns (default: `2e-4`).
     - **Epochs**: Number of passes through the dataset.
     - **Batch Size**: Number of samples per step.
     - **LoRA Rank**: Controls the size of the adapter (higher = more parameters to train).
   - **Advanced Parameters**: (Click to expand)
     - Adjust warmup steps, weight decay, gradient accumulation, and specific target modules.
5. **Review & Launch**: Give your run a name (or use the auto-generated one) and click **Start Training**.

**Monitoring**:
You will be redirected to the **Run Detail** page, where you can see:
- Real-time Loss curve
- Live training logs
- Hardware usage stats

---

## 5. Evaluating Models

To test how well a model performs on coding tasks:

1. Go to **Evaluation** in the sidebar.
2. **Configure Evaluation**:
   - **Task Name**: Name your evaluation run.
   - **Model**: Select the base model.
   - **Adapter**: (Optional) Select a trained LoRA adapter to evaluate.
   - **Dataset**: Choose an evaluation dataset (e.g., HumanEval, MBPP).
3. **Metrics**:
   - **Pass@k**: Standard metric for code generation. We typically measure Pass@1, Pass@5, and Pass@10.
   - **Samples**: Number of generations per problem (default: 20).
4. **Start Evaluation**: Click **Start Evaluation**.

**Results**:
The detailed report will show:
- Overall Pass@1/5/10 scores.
- **Error Analysis**: Breakdown of errors (Syntax, Runtime, Timeout, etc.).
- **Failure Cases**: View specific problems where the model failed, including the generated code and error messages.

---

## 6. Analysis Tools

### Playground
Interactive testing area.
1. Load a model (and optional adapter).
2. Type a prompt or select a template.
3. See the model's response in real-time.
4. Adjust temperature and max tokens on the fly.

### Compare Runs
Compare two training or evaluation runs side-by-side.
- **Config Diff**: See exactly what parameters differed between runs.
- **Metric Comparison**: Visual comparison of Loss curves or Pass@k scores.
- Useful for deciding which hyperparameter tuning worked best.

### Reports
Generate academic-style reports for your runs.
1. Select a completed run.
2. Choose format (HTML or Markdown).
3. Click **Generate**.
4. The report includes comprehensive details on configuration, results, and hardware environment, ready for sharing or publication.

---

## 7. Troubleshooting

**Q: The backend keeps restarting during training.**
**A:** Ensure you are using **Stable Mode** (Option 2) in the launcher. Development mode restarts the server on file changes, which kills active Python processes.

**Q: My training is OOM (Out of Memory).**
**A:** Try:
- Reducing `Batch Size`.
- Enabling `Gradient Accumulation` to compensate for smaller batches.
- Reducing `Max Sequence Length`.
- Using `4-bit` Quantization.

**Q: Evaluation shows 0% Pass@1.**
**A:** Check if your dataset format matches the model's expected prompt format. Also verify that the code execution environment (Python) is working correctly on your machine.

---

**Need more help?**
Check the technical documentation in `docs/project_documentation_en.md` for internal architecture details.
