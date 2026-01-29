# Java→C# Code Translation System Technical Documentation

> **Project Name**: CodeT5-based Cross-Lingual Code Translation System
> **Task**: Java Program-Level Code → C# Code Automatic Translation
> **Document Date**: 2026-01-24

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [System Architecture](#2-system-architecture)
3. [Tech Stack](#3-tech-stack)
4. [Datasets](#4-datasets)
5. [Model Training](#5-model-training)
6. [Post-Processing Pipeline](#6-post-processing-pipeline)
7. [Evaluation System](#7-evaluation-system)
8. [Workflow](#8-workflow)
9. [Experimental Results](#9-experimental-results)
10. [File Structure](#10-file-structure)

---

## 1. Project Overview

### 1.1 Research Background

Cross-lingual code translation is an important research direction in software engineering, aimed at automatically converting code from one programming language into syntactically and semantically equivalent code in another programming language. This project focuses on the **Java → C#** program-level code translation task.

### 1.2 Research Objectives

- Fine-tune a pre-trained code model (CodeT5) to achieve high-quality Java→C# code translation.
- Construct a multi-dimensional evaluation system to comprehensively measure translation quality.
- Design a post-processing pipeline to improve the compilability of the generated code.

### 1.3 Core Contributions

1. **Fine-tuning CodeT5 Model**: Fine-tuned on the XLCoST dataset for the Java→C# translation task.
2. **Three-Layer Post-Processing Pipeline**: Rule-based Cleaning → Formatting → Compiler-Aided Self-Healing.
3. **Multi-Dimensional Evaluation Framework**: A comprehensive evaluation of Semantic Consistency, Executability, and Code Quality.

---

## 2. System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     System Overall Architecture                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │ Data Prep    │───▶│ Model Train  │───▶│  Inference   │       │
│  │(Align/Preproc)│    │(CodeT5 FT)   │    │ (Pred/Trans) │       │
│  └──────────────┘    └──────────────┘    └──────────────┘       │
│         │                   │                   │               │
│         ▼                   ▼                   ▼               │
│  ┌──────────────────────────────────────────────────────┐       │
│  │               Post-Processing Pipeline               │       │
│  │  Layer 1: Rule Cleaning → Layer 2: Format → Layer 3: Self-Heal│
│  └──────────────────────────────────────────────────────┘       │
│                            │                                    │
│                            ▼                                    │
│  ┌──────────────────────────────────────────────────────┐       │
│  │               Multi-Dimensional Evaluation           │       │
│  │  BLEU │ CodeBLEU │ Compilation │ Exact Match │ Idioms │ Naming│
│  └──────────────────────────────────────────────────────┘       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Tech Stack

### 3.1 Core Frameworks

| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| **Deep Learning Framework** | PyTorch | 2.6.0 | Model Training & Inference |
| **Pre-trained Model Lib** | Hugging Face Transformers | 4.57.3 | Seq2Seq Training Framework |
| **Base Model** | Salesforce/codet5-base | - | Encoder-Decoder Transformer |
| **Syntax Parsing** | Tree-sitter | 0.22+ | AST Construction & CodeBLEU Calculation |
| **Evaluation Metric** | SacreBLEU | - | BLEU Score Calculation |

### 3.2 Model Architecture (CodeT5)

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Architecture Type** | T5ForConditionalGeneration | Encoder-Decoder Transformer |
| **Total Parameters** | ~220M | Approx. 220 Million Parameters |
| **Hidden Layer Dim** (d_model) | 768 | Token Embedding Dimension |
| **Encoder/Decoder Layers** | 12 | 12 Transformer Blocks each |
| **Attention Heads** | 12 | Multi-Head Self-Attention |
| **Feed Forward Dim** (d_ff) | 3072 | FFN Intermediate Dimension |
| **Vocab Size** | 32,100 | BPE Tokenization |
| **Max Sequence Length** | 512 | Input/Output Token Limit |
| **Dropout Rate** | 0.1 | Regularization |

### 3.3 Development Environment

- **Python**: 3.11+
- **CUDA**: 12.4
- **OS**: Windows 11
- **Compiler**: .NET SDK 7.0 (for C# compilation verification)

---

## 4. Datasets

### 4.1 Data Source: XLCoST Benchmark

XLCoST (Cross-Lingual Code Snippets) is a multi-lingual code translation benchmark dataset supporting 7 programming languages.

**Citation**:
```
Zhu et al., "XLCoST: A Benchmark Dataset for Cross-lingual Code Intelligence", 
arXiv:2206.08474, 2022
```

### 4.2 Data Statistics

| Dataset | Java Samples | C# Samples | Aligned Samples |
|---------|--------------|------------|-----------------|
| **Train Set** | 9,623 | 9,345 | ~9,000 |
| **Valid Set** | 481 | 472 | ~460 |
| **Test Set** | 911 | 899 | 894 |

### 4.3 Data Format

Each sample contains:
- `text`: Problem description (Natural Language)
- `code`: Source Code

**Example** (Java):
```json
{
  "text": "Maximum Prefix Sum | Implementation of the above approach...",
  "code": "public static void main(String[] args) { ... }"
}
```

### 4.4 Data Alignment Strategy

Due to sample count mismatch between original Java (911) and C# (899) datasets, a **Description Text Exact Match** strategy is used for alignment:

1. Extract `text` field for each sample, truncate description before `|`.
2. Group by description to build Java/C# description→code mapping.
3. Take the intersection of descriptions from both sides to generate aligned sample pairs.
4. Perform code-level deduplication to remove duplicate code snippets.

**Implementation File**: `align_datasets.py`

---

## 5. Model Training

### 5.1 Training Configuration

| Hyperparameter | Value | Description |
|----------------|-------|-------------|
| **Learning Rate** | 3e-5 | AdamW Optimizer |
| **Batch Size (per device)** | 4 | Single GPU Batch Size |
| **Gradient Accumulation** | 2 | Effective Batch Size = 8 |
| **Epochs** | 3 | Training Epochs |
| **Weight Decay** | 0.01 | L2 Regularization |
| **Warmup Steps** | 500 | Linear Learning Rate Warmup |
| **Max Seq Length** | 512 | Input/Output Token Limit |
| **Mixed Precision** | FP16 | Accelerated Training |
| **Save Strategy** | Per epoch | Checkpoint Saving |

### 5.2 Input Format

Prompt format used during training:
```
translate Java to C#: [Java Code]
```

**Label**: Corresponding C# Code

### 5.3 Training Process

```python
# Pseudocode
tokenizer = AutoTokenizer.from_pretrained("Salesforce/codet5-base")
model = AutoModelForSeq2SeqLM.from_pretrained("Salesforce/codet5-base")

trainer = Seq2SeqTrainer(
    model=model,
    train_dataset=train_dataset,   # Aligned Java-C# Pairs
    eval_dataset=valid_dataset,
    training_args=Seq2SeqTrainingArguments(
        num_train_epochs=3,
        learning_rate=3e-5,
        per_device_train_batch_size=4,
        gradient_accumulation_steps=2,
        fp16=True,
        ...
    )
)
trainer.train()
```

### 5.4 Training Results

| Epoch | Train Loss | Valid Loss |
|-------|------------|------------|
| 1 | 0.0718 | 0.0669 |
| 2 | 0.0434 | 0.0584 |
| 3 | 0.0588 | 0.0570 |

> Training loss dropped from initial ~11.22 to 0.0588, a reduction of **99.5%**

---

## 6. Post-Processing Pipeline

### 6.1 Three-Layer Architecture

Generated C# code may contain Java residual syntax or format issues. The post-processing pipeline improves code quality through three layers:

```
┌────────────────────────────────────────────────────────────┐
│              Post-Processing Pipeline (PostProcessor)        │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  Layer 1: Rule Cleaning (Regex-based Cleaning)             │
│  ├── Remove Markdown Code Blocks                           │
│  ├── Remove LLM Session Text                               │
│  ├── Primitive Type Mapping (boolean→bool, Integer→int)    │
│  ├── String Method Mapping (.length()→.Length)             │
│  ├── Collection Type Mapping (ArrayList→List, HashMap→Dict)│
│  ├── I/O Mapping (System.out.println→Console.WriteLine)    │
│  ├── Annotation Handling (@Override→Remove, @Deprecated→[Obs])│
│  ├── Java Specific Syntax Removal (package, import, throws)│
│  └── Method Name Case Correction (toString→ToString)       │
│                         ▼                                  │
│  Layer 2: Syntax Formatting (dotnet format)                │
│  └── Call dotnet format to unify code style                │
│                         ▼                                  │
│  Layer 3: Compiler-Aided Self-Healing                      │
│  ├── Run dotnet build to get compilation errors            │
│  ├── Parse error codes (CS1002, CS0103, CS0246, etc.)      │
│  ├── Apply Heuristic Repairs:                              │
│  │   ├── CS1002: Add missing semicolon                     │
│  │   ├── CS0103/CS0246: Add using statements               │
│  │   ├── CS1955: Remove parens from property calls         │
│  │   └── CS1061: Replace Java methods with C# equivalents  │
│  └── Iterative Repair (Max 3 rounds)                       │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

### 6.2 Key Conversion Rules

| Java Syntax | C# Equivalent | Category |
|-------------|---------------|----------|
| `boolean` | `bool` | Primitive Type |
| `Integer` | `int` | Wrapper Type |
| `.length()` | `.Length` | String Property |
| `.charAt(i)` | `[i]` | Character Access |
| `.substring(a,b)` | `.Substring(a,b)` | String Method |
| `ArrayList<T>` | `List<T>` | Collection Type |
| `HashMap<K,V>` | `Dictionary<K,V>` | Map Type |
| `.add()` | `.Add()` | Collection Method |
| `.size()` | `.Count` | Collection Size |
| `System.out.println()` | `Console.WriteLine()` | Standard Output |
| `@Override` | (Remove) | Annotation |
| `extends` | `:` | Inheritance Syntax |
| `implements` | `:` | Interface Implementation |

**Implementation File**: `post_process.py`

---

## 7. Evaluation System

### 7.1 Evaluation Dimensions

This project adopts a **Three-Dimension Multi-Metric** evaluation system:

```
┌─────────────────────────────────────────────────────────────┐
│                      Evaluation Dimension Framework         │
├───────────────┬──────────────────┬─────────────────────────┤
│  Dim 1: Semantics│  Dim 2: Executable │  Dim 3: Code Quality   │
├───────────────┼──────────────────┼─────────────────────────┤
│ • BLEU        │ • CompilationRate│ • C# Idiom Density       │
│ • CodeBLEU    │ • SyntaxValidity │ • Naming Convention Score│
│   ├─ N-gram   │   (AST Parsing)  │   (PascalCase Check)     │
│   ├─ Weighted │                  │ • Java Residue Check     │
│   ├─ AST      │                  │                         │
│   └─ DataFlow │                  │                         │
│ • Exact Match │                  │                         │
└───────────────┴──────────────────┴─────────────────────────┘
```

### 7.2 Metric Details

#### 7.2.1 BLEU (Bilingual Evaluation Understudy)

Traditional machine translation metric, calculating n-gram overlap between generated and reference code.

```python
from sacrebleu import corpus_bleu
bleu = corpus_bleu(predictions, references)
```

#### 7.2.2 CodeBLEU

Evaluation metric designed specifically for code, synthesizing four sub-metrics:

$$\text{CodeBLEU} = \alpha \cdot \text{BLEU}_{ngram} + \beta \cdot \text{BLEU}_{weighted} + \gamma \cdot \text{Match}_{AST} + \delta \cdot \text{Match}_{DataFlow}$$

Default Weights: $\alpha = \beta = \gamma = \delta = 0.25$

| Sub-metric | Calculation Method | Significance |
|------------|--------------------|--------------|
| **N-gram Match** | Standard BLEU | Token level match |
| **Weighted N-gram** | Keyword Weighted BLEU | Emphasize syntax keywords |
| **Syntax Match (AST)** | Tree-sitter AST Structure Compare | Syntactic structural similarity |
| **DataFlow Match** | Variable Define-Use Chain Analysis | Semantic logic similarity |

**Implementation Files**: `metrics/codebleu_eval.py`, `metrics/native_codebleu/`

#### 7.2.3 Compilation Rate

Use .NET SDK to compile generated C# code:

```python
result = subprocess.run(["dotnet", "build", project_dir], ...)
compilation_rate = compiled_count / total_count
```

**Implementation File**: `metrics/compilation_eval.py`

#### 7.2.4 Exact Match Rate

Compare if generated code is exactly the same as reference code after stripping whitespace:

```python
def normalize(code):
    return re.sub(r'\s+', '', code)

exact_match = sum(normalize(pred) == normalize(ref) for pred, ref in pairs) / len(pairs)
```

**Implementation File**: `metrics/exact_match_eval.py`

#### 7.2.5 C# Idiom Density

Detect the frequency of C# specific idioms in generated code:

| Idiom Category | Detection Pattern |
|----------------|-------------------|
| **LINQ** | `.Where()`, `.Select()`, `.FirstOrDefault()`, etc. |
| **var Keyword** | `var x = ...` |
| **foreach** | `foreach (var x in ...)` |
| **Auto Properties** | `{ get; set; }` |
| **Null Conditional** | `?.`, `??`, `??=` |
| **String Interpolation** | `$"... {var} ..."` |
| **Expression Body** | `=> expression;` |
| **async/await** | `async`, `await` |
| **Pattern Matching** | `is Type name`, `switch` expressions |

**Implementation File**: `metrics/idiom_eval.py`

#### 7.2.6 Naming Convention Score

Detect if method names follow C# PascalCase convention:

```python
def is_pascal_case(name):
    return re.match(r'^[A-Z][a-zA-Z0-9]*$', name) is not None

naming_score = pascal_case_methods / total_methods
```

**Implementation File**: `metrics/naming_eval.py`

---

## 8. Workflow

### 8.1 Complete Workflow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        Complete Workflow                        │
└─────────────────────────────────────────────────────────────────┘

1. Data Preparation Phase
   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
   │ Download    │───▶│ Data Align   │───▶│ Preprocess  │
   │ XLCoST Dataset│    │ (By Descrip) │    │ (Token/Trunc)│
   └─────────────┘    └─────────────┘    └─────────────┘
         │                  │                  │
         ▼                  ▼                  ▼
   xlcost_data/      align_datasets.py   train_data.py

2. Model Training Phase
   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
   │ Load Config │───▶│ Load Model   │───▶│ Train Loop  │
   │ (Hyperparams)│    │ (CodeT5)    │    │ (Epoch Iter)│
   └─────────────┘    └─────────────┘    └─────────────┘
         │                  │                  │
         ▼                  ▼                  ▼
   train_config.py   Salesforce/codet5   train_model.py
                                               │
                                               ▼
                                    fine_tuned_codet5_java_csharp/

3. Evaluation Phase
   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
   │ Load TestSet│───▶│ Inference    │───▶│ PostProcess │
   │ (Aligned)   │    │ (Beam=1)    │    │ (3-Layer Pipe)│
   └─────────────┘    └─────────────┘    └─────────────┘
         │                                      │
         ▼                                      ▼
   aligned/*.json                        post_process.py
                                               │
   ┌─────────────┐    ┌─────────────┐          │
   │ Calc Metric │◀───│ Compare Ref  │◀─────────┘
   │ (Multi-Dim) │    │   Code      │
   └─────────────┘    └─────────────┘
         │
         ▼
   metrics/*.py
         │
         ▼
   ┌─────────────────────────────────────────┐
   │            Evaluation Output            │
   │  evaluation_summary.json                │
   │  evaluation_results_multidim.csv        │
   │  research_paper_report.md               │
   └─────────────────────────────────────────┘
```

### 8.2 Command Line Execution

```bash
# 1. Align Datasets
python align_datasets.py

# 2. Train Model
python train_model.py

# 3. Evaluate Model
python evaluate_model.py

# 4. Generate Report
python generate_report.py
```

---

## 9. Experimental Results

### 9.1 Key Metrics

| Dimension | Metric | Value | Description |
|-----------|--------|-------|-------------|
| **Semantics** | BLEU | **100.00** | Traditional n-gram match |
| **Semantics** | CodeBLEU | **0.9390** | AST + DataFlow Composite |
| | ├─ Syntax (AST) | 0.9324 | Syntax Tree Structure Match |
| | └─ DataFlow | 0.9471 | Variable Logic Flow Match |
| **Executable** | Compilation Rate | 69.24% | dotnet build test |
| **Quality** | Naming Convention | **69.1%** | PascalCase Compliance Rate |
| **Quality** | C# Idioms | 0.12/sample | LINQ/var/foreach |

### 9.2 Model Comparison (Fine-tuned vs Base)

| Metric | Base Model | Fine-tuned Model | Improvement |
|--------|------------|------------------|-------------|
| BLEU | 54.17 | **100.00** | +45.83 |
| CodeBLEU | 0.1029 | **0.9390** | +0.8360 |
| Syntax (AST) | 0.0474 | **0.9324** | +0.8850 |
| DataFlow | 0.0467 | **0.9471** | +0.9004 |
| Func Pass Rate | 0.00% | **72.06%** | +72.06% |

> **BLEU Improvement**: Improved from 54.17 to 100.00, an increase of **84.6%**

### 9.3 Case Study

**Java Input**:
```java
import java.util.*; 
class GFG { 
    static void countSubarray(int[] arr, int n) { 
        int L = 0, R = 0; 
        int mx = Integer.MIN_VALUE; 
        for (int i = 0; i < n; i++) 
            mx = Math.max(mx, arr[i]); 
        // ...
    } 
}
```

**C# Output**:
```csharp
using System; 
class GFG { 
    static void countSubarray(int[] arr, int n) { 
        int L = 0, R = 0; 
        int mx = int.MinValue; 
        for (int i = 0; i < n; i++) 
            mx = Math.Max(mx, arr[i]); 
        // ...
    } 
}
```

**Key Conversions**:
- `import java.util.*` → `using System`
- `Integer.MIN_VALUE` → `int.MinValue`
- `Math.max` → `Math.Max`

---

## 10. File Structure

```
kabul_vipin_edition/
├── Core Code
│   ├── train_model.py        # Main Training Script
│   ├── train_config.py       # Training Hyperparams
│   ├── train_data.py         # Data Loading & Alignment
│   ├── train_report.py       # Training Report Gen
│   ├── align_datasets.py     # Test Set Data Alignment
│   ├── evaluate_model.py     # Multi-Dim Evaluation Main Script
│   ├── post_process.py       # Post-Processing Pipeline
│   └── generate_report.py    # Eval Report Generation
│
├── Metrics (metrics/)
│   ├── __init__.py
│   ├── codebleu_eval.py      # CodeBLEU Calc
│   ├── compilation_eval.py   # Compilation Rate Eval
│   ├── exact_match_eval.py   # Exact Match Rate
│   ├── idiom_eval.py         # C# Idiom Density
│   ├── naming_eval.py        # Naming Convention Score
│   ├── syntax_validity_eval.py # AST Syntax Validity
│   └── native_codebleu/      # Native Tree-sitter Impl
│
├── Datasets (xlcost_data/)
│   ├── data/
│   │   ├── Java-program-level/   # Java Data
│   │   │   ├── train.json
│   │   │   ├── valid.json
│   │   │   └── test.json
│   │   ├── Csharp-program-level/ # C# Data
│   │   │   ├── train.json
│   │   │   ├── valid.json
│   │   │   └── test.json
│   │   └── aligned/              # Aligned Data
│   │       ├── java_aligned.json
│   │       └── csharp_aligned.json
│   └── README.md
│
├── Model Output (fine_tuned_codet5_java_csharp/)
│   ├── final_model/          # Final Model Weights
│   ├── training_logs.json    # Training Logs
│   └── train_report.md       # Training Report
│
├── Evaluation Results
│   ├── evaluation_summary.json       # Eval Summary
│   ├── evaluation_results_multidim.csv # Detailed Results
│   └── research_paper_report.md      # Research Report
│
└── Others
    ├── AIMODELTRAINING.ipynb  # Jupyter Notebook
    ├── verify_setup.py        # Environment Verification
    └── .gitignore
```

---

## Appendix

### A. Dependencies

```
torch>=2.0.0
transformers>=4.30.0
datasets
sacrebleu
tree-sitter>=0.22.0
tree-sitter-c-sharp
pandas
tqdm
psutil
```

### B. Hardware Requirements

| Component | Recommended Config |
|-----------|--------------------|
| GPU | NVIDIA RTX 3080+ (16GB+ VRAM) |
| RAM | 32GB+ |
| Storage | 50GB+ SSD |
| CUDA | 12.0+ |

### C. References

1. Wang et al., "CodeT5: Identifier-aware Unified Pre-trained Encoder-Decoder Models for Code Understanding and Generation", EMNLP 2021
2. Zhu et al., "XLCoST: A Benchmark Dataset for Cross-lingual Code Intelligence", arXiv 2022
3. Ren et al., "CodeBLEU: a Method for Automatic Evaluation of Code Synthesis", arXiv 2020

---

*Document End*
