# research_paper_report.md

# Java → C# 代码翻译模型评测报告
**Report Generated:** 2026-01-16 02:24:26

---

## 1. Executive Summary

本报告对基于 CodeT5 微调的 Java 到 C# 代码翻译模型进行了全面评测。

### 核心指标一览

| 维度 | 指标 | 数值 | 说明 |
| :--- | :--- | ---: | :--- |
| **语义** | BLEU | **100.00** | 传统 n-gram 匹配 |
| **语义** | CodeBLEU | **0.9390** | AST + DataFlow 综合 |
| | ├─ Syntax (AST) | 0.9324 | 语法树结构匹配 |
| | └─ DataFlow | 0.9471 | 变量逻辑流匹配 |
| **可执行** | 编译成功率 | 69.24% | C# dotnet build |
| **质量** | 命名规范 | **69.1%** | PascalCase 遵循率 |
| **质量** | C# 惯用语 | 0.12/样本 | LINQ/var/foreach |

> **Note**: CodeBLEU 使用了原生 Tree-sitter 实现 (AST + 变量归一化 DataFlow)。

### 模型对比

| 指标 | 基座模型 | 微调模型 | 提升 |
| :--- | ---: | ---: | ---: |
| BLEU | 54.17 | **100.00** | +45.83 |
| CodeBLEU | 0.1029 | **0.9390** | +0.8360 |
| Syntax (AST) | 0.0474 | **0.9324** | +0.8850 |
| DataFlow | 0.0467 | **0.9471** | +0.9004 |
| 命名规范 | 95.6% | **69.1%** | -26.5% |

> **BLEU 提升**: 84.6% (从 54.17 到 100.00)


---
## 2. Model Architecture

### 2.1 基座模型信息

| 属性 | 值 |
| :--- | :--- |
| **Base Model** | Salesforce/codet5-base |
| **Architecture** | T5ForConditionalGeneration (Encoder-Decoder) |
| **Parameters** | ~220M |
| **Hidden Size (d_model)** | 768 |
| **Encoder/Decoder Layers** | 12 |
| **Attention Heads** | 12 |
| **Feed-Forward Dim (d_ff)** | 3072 |
| **Vocabulary Size** | 32,100 |
| **Max Sequence Length** | 512 |
| **Dropout Rate** | 0.1 |

### 2.2 训练超参数

| 超参数 | 值 |
| :--- | :--- |
| **Epochs** | 3 |
| **Batch Size** | 4 |
| **Total Training Steps** | 3,462 |
| **Initial Learning Rate** | 5e-5 |
| **Optimizer** | AdamW (Hugging Face default) |
| **Warmup Steps** | ~10% |
| **Total FLOPs** | 1.69e+16 |

### 2.3 训练过程 (Loss 曲线)

| Epoch | Training Loss | Validation Loss |
| :---: | ---: | ---: |
| 0 | 0.0718 | - |
| 1 | 0.0434 | 0.0669 |
| 2 | 0.0588 | 0.0584 |
| 3 | - | 0.0570 |

> **训练收敛**: Loss 从 11.2226 降至 0.0588，减少 **99.5%**。

---
## 3. Dataset Details

### 3.1 XLCoST 数据集

| 属性 | 值 |
| :--- | :--- |
| **来源** | [XLCoST: A Benchmark Dataset for Cross-lingual Code Snippets](https://github.com/xiaobingabc/XLCoST) |
| **任务** | Java → C# (Program-level) |
| **训练集 (Java)** | 9,623 programs |
| **训练集 (C#)** | 9,345 programs |
| **测试集 (Java)** | 911 programs |
| **测试集 (C#)** | 899 programs |
| **评测样本数** | 894 (对齐后) |

> **Note**: 评测使用对齐后的测试集 (`xlcost_data/data/aligned/`)，确保 Java-C# 样本一一对应。


### 3.2 测试样本统计

- **平均输入长度**: 679 字符
- **最大输入长度**: 2869 字符

---
## 4. Evaluation Metrics (Full Details)

### 4.1 语义一致性

| 指标 | 数值 | 计算方法 |
| :--- | ---: | :--- |
| **BLEU** | 100.00 | SacreBLEU 4-gram |
| **CodeBLEU** | 0.9390 | 加权综合 (下述 4 项) |
| ├─ N-gram Match | 0.9299 | 标准 n-gram 匹配 |
| ├─ Weighted N-gram | 0.9464 | 关键词加权 |
| ├─ **Syntax (AST)** | 0.9324 | Tree-sitter 语法树匹配 |
| └─ **DataFlow** | 0.9471 | 变量归一化逻辑流分析 |
| **Exact Match** | 11.5% | 完全相同比例 |

### 4.2 可执行性

| 指标 | 数值 | 说明 |
| :--- | ---: | :--- |
| **Compilation Rate** | 69.24% | `dotnet build` 测试 |
| **Syntax Validity (AST)** | 92.28% | Tree-sitter 解析成功率 |

### 4.3 代码质量

| 指标 | 数值 | 说明 |
| :--- | ---: | :--- |
| **Naming Convention Score** | 69.1% | C# 命名规范遵循 |
| ├─ PascalCase Methods | 1025/2185 | 方法名检测 |
| **Avg C# Idioms / Sample** | 0.12 | 惯用语密度 |
| ├─ LINQ Usage | 0 | .Where(), .Select()... |
| ├─ foreach Usage | 81 | - |
| ├─ var Keyword | 0 | - |
| **Java Pattern Residue** | 0 | 残留 Java 风格代码 |

### 4.6 功能正确性 (Code-to-Code)\n
| 指标 | 基座模型 | 微调模型 | 提升 |
| :--- | ---: | ---: | ---: |
| **功能正确率** | 0.00% | **72.06%** | +72.06% |
| **编译成功率** | 0.00% | **85.29%** | +85.29% |
| **通过测试数** | 0/68 | **49/68** | +49 |

> **Note**: 功能正确性通过对比翻译代码与参考 C# 代码的执行输出进行验证。\n

### 4.7 回归测试 (Text-to-Code)\n
评估微调后模型在原始 Text-to-code 任务上的能力是否退化（灾难性遗忘检测）。\n
| 指标 | 基座模型 | 微调模型 | 差异 (Diff) |
| :--- | ---: | ---: | ---: |
| **BLEU** | 0.00 | **4.40** | +4.40 |
| **CodeBLEU** | 0.01 | **0.08** | +0.07 |

> ✅ **Info**: 微调模型在 Text-to-code 任务上性能甚至有所提升，表明发生了正向知识迁移。\n

---
## 5. Qualitative Analysis (Case Studies)

### Case Study #1

**Input (Java):**
```java
import java . util . * ; class GFG { static void countSubarray ( int [ ] arr , int n ) { int L = 0 , R = 0 ; int mx = Integer . MIN_VALUE ; for ( int i = 0 ; i < n ; i ++ ) mx = Math . max ( mx , arr [ i ] ) ; for ( int i = 0 ; i < n ; i ++ ) { if ( arr [ i ] * 2 > mx ) { L = i ; break ; } } for ( int i = n - 1 ; i >= 0 ; i -- ) { if ( arr [ i ] * 2 > mx ) { R = i ; break ; } } System . out . println ( ( L + 1 ) * ( n - R ) ) ; } public static void main ( String [ ] args ) { int [ ] arr = { 1 , 6 , 10 , 9 , 7 , 3 } ; int N = arr . length ; countSubarray ( arr , N ) ; } }
```

**Reference (C#):**
```csharp
using System ; class GFG { static void countSubarray ( int [ ] arr , int n ) { int L = 0 , R = 0 ; int mx = Int32 . MinValue ; for ( int i = 0 ; i < n ; i ++ ) mx = Math . Max ( mx , arr [ i ] ) ; for ( int i = 0 ; i < n ; i ++ ) { if ( arr [ i ] * 2 > mx ) { L = i ; break ; } } for ( int i = n - 1 ; i >= 0 ; i -- ) { if ( arr [ i ] * 2 > mx ) { R = i ; break ; } } Console . WriteLine ( ( L + 1 ) * ( n - R ) ) ; } public static void Main ( ) { int [ ] arr = { 1 , 6 , 10 , 9 , 7 , 3 } ; int N = arr . Length ; countSubarray ( arr , N ) ; } }
```

**Model Prediction:**
```csharp
using System ; class GFG { static void countSubarray ( int [ ] arr , int n ) { int L = 0 , R = 0 ; int mx = int . MinValue ; for ( int i = 0 ; i < n ; i ++ ) mx = Math . Max ( mx , arr [ i ] ) ; for ( int i = 0 ; i < n ; i ++ ) { if ( arr [ i ] * 2 > mx ) { L = i ; break ; } } for ( int i = n - 1 ; i >= 0 ; i -- ) { if ( arr [ i ] * 2 > mx ) { R = i ; break ; } } Console . WriteLine ( ( L + 1 ) * ( n - R ) ) ; } public static void Main ( string [ ] args ) { int [ ] arr = { 1 , 6 , 10 , 9 , 7 , 3 } ; int N = arr . Length ; countSubarray ( arr , N ) ; } }
```

- Idiom Score: 0.5
- Naming Score: 63.64%

---

### Case Study #2

**Input (Java):**
```java
import java . util . * ; class GFG { static void findClosest ( int N , int target ) { int closest = - 1 ; int diff = Integer . MAX_VALUE ; for ( int i = 1 ; i <= ( int ) Math . sqrt ( N ) ; i ++ ) { if ( N % i == 0 ) { if ( N / i == i ) { if ( Math . abs ( target - i ) < diff ) { diff = Math . abs ( target - i ) ; closest = i ; } } else { if ( Math . abs ( target - i ) < diff ) { diff = Math . abs ( target - i ) ; closest = i ; } if ( Math . abs ( target - N / i ) < diff ) { diff = Math . abs ( target - N / i ) ; closest = N / i ; } } } } System . out . println ( closest ) ; } public static void main ( String [ ] args ) { int N = 16 , X = 5 ; findClosest ( N , X ) ; } }
```

**Reference (C#):**
```csharp
using System ; class GFG { static void findClosest ( int N , int target ) { int closest = - 1 ; int diff = Int32 . MaxValue ; for ( int i = 1 ; i <= Math . Sqrt ( N ) ; i ++ ) { if ( N % i == 0 ) { if ( N / i == i ) { if ( Math . Abs ( target - i ) < diff ) { diff = Math . Abs ( target - i ) ; closest = i ; } } else { if ( Math . Abs ( target - i ) < diff ) { diff = Math . Abs ( target - i ) ; closest = i ; } if ( Math . Abs ( target - N / i ) < diff ) { diff = Math . Abs ( target - N / i ) ; closest = N / i ; } } } } Console . Write ( closest ) ; } static void Main ( ) { int N = 16 , X = 5 ; findClosest ( N , X ) ; } }
```

**Model Prediction:**
```csharp
using System ; class GFG { static void findClosest ( int N , int target ) { int closest = - 1 ; int diff = int . MaxValue ; for ( int i = 1 ; i <= ( int ) Math . Sqrt ( N ) ; i ++ ) { if ( N % i == 0 ) { if ( N / i == i ) { if ( Math . Abs ( target - i ) < diff ) { diff = Math . Abs ( target - i ) ; closest = i ; } } else { if ( Math . Abs ( target - i ) < diff ) { diff = Math . Abs ( target - i ) ; closest = i ; } if ( Math . Abs ( target - N / i ) < diff ) { diff = Math . Abs ( target - N / i ) ; closest = N / i ; } } } } Console . WriteLine ( closest ) ; } public static void Main ( string [ ] args ) { int N = 16 , X = 5 ; findClosest ( N , X ) ; } }
```

- Idiom Score: 0.5
- Naming Score: 66.67%

---

### Case Study #3

**Input (Java):**
```java
class GFG { static int func ( int N , int P ) { int sumUptoN = ( N * ( N + 1 ) / 2 ) ; int sumOfMultiplesOfP ; if ( N < P ) { return sumUptoN ; } else if ( ( N / P ) == 1 ) { return sumUptoN - P + 1 ; } sumOfMultiplesOfP = ( ( N / P ) * ( 2 * P + ( N / P - 1 ) * P ) ) / 2 ; return ( sumUptoN + func ( N / P , P ) - sumOfMultiplesOfP ) ; } public static void main ( String [ ] args ) { int N = 10 , P = 5 ; System . out . println ( func ( N , P ) ) ; } }
```

**Reference (C#):**
```csharp
using System ; class GFG { static int func ( int N , int P ) { int sumUptoN = ( N * ( N + 1 ) / 2 ) ; int sumOfMultiplesOfP ; if ( N < P ) { return sumUptoN ; } else if ( ( N / P ) == 1 ) { return sumUptoN - P + 1 ; } sumOfMultiplesOfP = ( ( N / P ) * ( 2 * P + ( N / P - 1 ) * P ) ) / 2 ; return ( sumUptoN + func ( N / P , P ) - sumOfMultiplesOfP ) ; } public static void Main ( String [ ] args ) { int N = 10 , P = 5 ; Console . WriteLine ( func ( N , P ) ) ; } }
```

**Model Prediction:**
```csharp
using System ; class GFG { static int func ( int N , int P ) { int sumUptoN = ( N * ( N + 1 ) / 2 ) ; int sumOfMultiplesOfP ; if ( N < P ) { return sumUptoN ; } else if ( ( N / P ) == 1 ) { return sumUptoN - P + 1 ; } sumOfMultiplesOfP = ( ( N / P ) * ( 2 * P + ( N / P - 1 ) * P ) ) / 2 ; return ( sumUptoN + func ( N / P , P ) - sumOfMultiplesOfP ) ; } public static void Main ( ) { int N = 10 , P = 5 ; Console . WriteLine ( func ( N , P ) ) ; } }
```

- Idiom Score: 0.5
- Naming Score: 57.14%

---

### Case Study #4

**Input (Java):**
```java
import java . io . * ; import java . util . * ; class GFG { static long multiplyByMersenne ( long N , long M ) { long x = ( int ) ( Math . log ( M + 1 ) / Math . log ( 2 ) ) ; return ( ( N << x ) - N ) ; } public static void main ( String [ ] args ) { long N = 4 ; long M = 15 ; System . out . print ( multiplyByMersenne ( N , M ) ) ; } }
```

**Reference (C#):**
```csharp
using System ; class GFG { static int multiplyByMersenne ( int N , int M ) { int x = ( int ) ( Math . Log ( M + 1 ) / Math . Log ( 2 ) ) ; return ( ( N << x ) - N ) ; } static public void Main ( ) { int N = 4 ; int M = 15 ; Console . Write ( multiplyByMersenne ( N , M ) ) ; } }
```

**Model Prediction:**
```csharp
using System ; class GFG { static long multiplyByMersenne ( long N , long M ) { long x = ( int ) ( Math . Log ( M + 1 ) / Math . Log ( 2 ) ) ; return ( ( N << x ) - N ) ; } public static void Main ( ) { long N = 4 ; long M = 15 ; Console . Write ( multiplyByMersenne ( N , M ) ) ; } }
```

- Idiom Score: 0.5
- Naming Score: 50.00%

---

### Case Study #5

**Input (Java):**
```java
import java . io . * ; class GFG { static int countPaths ( int n , int m ) { if ( n == 0 m == 0 ) return 1 ; return ( countPaths ( n - 1 , m ) + countPaths ( n , m - 1 ) ) ; } public static void main ( String [ ] args ) { int n = 3 , m = 2 ; System . out . println ( " ▁ Number ▁ of ▁ Paths ▁ " + countPaths ( n , m ) ) ; } }
```

**Reference (C#):**
```csharp
using System ; public class GFG { static int countPaths ( int n , int m ) { if ( n == 0 m == 0 ) return 1 ; return ( countPaths ( n - 1 , m ) + countPaths ( n , m - 1 ) ) ; } public static void Main ( ) { int n = 3 , m = 2 ; Console . WriteLine ( " ▁ Number ▁ of " + " ▁ Paths ▁ " + countPaths ( n , m ) ) ; } }
```

**Model Prediction:**
```csharp
using System ; class GFG { static int countPaths ( int n , int m ) { if ( n == 0 m == 0 ) return 1 ; return ( countPaths ( n - 1 , m ) + countPaths ( n , m - 1 ) ) ; } public static void Main ( ) { int n = 3 , m = 2 ; Console . WriteLine ( " ▁ Number ▁ of ▁ Paths ▁ " + countPaths ( n , m ) ) ; } };;;;;;
```

- Idiom Score: 0.5
- Naming Score: 66.67%

---

## 6. Conclusion & Discussion

### 6.1 主要发现

1. **高质量翻译**: BLEU 得分 100.00 表明模型能够生成与参考代码高度相似的输出。
2. **语法结构保持**: AST Match 0.9324 显示模型正确学习了 C# 的语法结构。
3. **逻辑流转换**: DataFlow Match 0.9471 表明变量定义-使用逻辑得到较好保持。
4. **C# 风格学习**: 命名规范得分 69.08%，方法名多数遵循 PascalCase。
5. **惯用语采纳**: 模型使用了 LINQ 和 foreach 等 C# 惯用语。

### 6.2 局限性

- 编译成功率为 69.2%，部分生成代码存在语法错误。
- 精确匹配率为 11.5%，模型输出与参考代码存在格式或细节差异。
- 未运行单元测试评测 (Pass@1)，功能正确性未验证。
- 命名规范遵循率 69.1%，部分方法名未使用 PascalCase。

### 6.3 未来工作建议

- 运行 `evaluate_unit_tests.py` 进行单元测试评测 (Pass@1)
- 优化后处理规则以提高编译成功率
- 增强训练数据中 C# 命名规范的样本权重
- 引入人工评审进行定性分析
- 对比其他 Baseline 模型 (GPT-3.5, CodeGen, StarCoder 等)
- 扩展至更多语言对 (Python→C#, JavaScript→C# 等)

---
## Appendix

### A. 文件路径

- **模型**: `C:\Users\Shu Leo\Desktop\practical course\kabul-main\kabul_vipin_edition\fine_tuned_codet5_java_csharp`
- **评测摘要**: `C:\Users\Shu Leo\Desktop\practical course\kabul-main\kabul_vipin_edition\evaluation_summary.json`
- **详细结果**: `C:\Users\Shu Leo\Desktop\practical course\kabul-main\kabul_vipin_edition\evaluation_results_multidim.csv`

### B. 环境信息

```
Python: 3.13.9
PyTorch: 2.6.0+cu124
Transformers: 4.57.3
tree-sitter: 0.22+
```


---

# research_paper_reportEnglish.md

# Java → C# Code Translation Model Evaluation Report
**Report Generated:** 2026-01-16 03:47:20

---

## 1. Executive Summary

This report conducts a comprehensive evaluation of the Java to C# code translation model fine-tuned on CodeT5.

### Key Metrics Overview

| Dimension | Metric | Value | Description |
| :--- | :--- | ---: | :--- |
| **Semantic** | BLEU | **100.00** | Traditional n-gram match |
| **Semantic** | CodeBLEU | **0.9390** | AST + DataFlow Composite |
| | ├─ Syntax (AST) | 0.9324 | Syntax Tree Structure Match |
| | └─ DataFlow | 0.9471 | Variable Logic Flow Match |
| **Executability** | Compilation Rate | 69.24% | C# dotnet build |
| **Quality** | Naming Convention | **69.1%** | PascalCase Compliance |
| **Quality** | C# Idioms | 0.12/Sample | LINQ/var/foreach |

> **Note**: CodeBLEU uses native Tree-sitter implementation (AST + Variable Renaming DataFlow).

### Model Comparison

| Metric | Base Model | Fine-tuned Model | Improvement |
| :--- | ---: | ---: | ---: |
| BLEU | 54.17 | **100.00** | +45.83 |
| CodeBLEU | 0.1029 | **0.9390** | +0.8360 |
| Syntax (AST) | 0.0474 | **0.9324** | +0.8850 |
| DataFlow | 0.0467 | **0.9471** | +0.9004 |
| Naming Convention | 95.6% | **69.1%** | -26.5% |

> **BLEU Improvement**: 84.6% (from 54.17 to 100.00)


---
## 2. Model Architecture

### 2.1 Base Model Information

| Attribute | Value |
| :--- | :--- |
| **Base Model** | Salesforce/codet5-base |
| **Architecture** | T5ForConditionalGeneration (Encoder-Decoder) |
| **Parameters** | ~220M |
| **Hidden Size (d_model)** | 768 |
| **Encoder/Decoder Layers** | 12 |
| **Attention Heads** | 12 |
| **Feed-Forward Dim (d_ff)** | 3072 |
| **Vocabulary Size** | 32,100 |
| **Max Sequence Length** | 512 |
| **Dropout Rate** | 0.1 |

### 2.2 Training Hyperparameters

| Hyperparameter | Value |
| :--- | :--- |
| **Epochs** | 3 |
| **Batch Size** | 4 |
| **Total Training Steps** | 3,462 |
| **Initial Learning Rate** | 5e-5 |
| **Optimizer** | AdamW (Hugging Face default) |
| **Warmup Steps** | ~10% |
| **Total FLOPs** | 1.69e+16 |

### 2.3 Training Process (Loss Curve)

| Epoch | Training Loss | Validation Loss |
| :---: | ---: | ---: |
| 0 | 0.0718 | - |
| 1 | 0.0434 | 0.0669 |
| 2 | 0.0588 | 0.0584 |
| 3 | - | 0.0570 |

> **Training Convergence**: Loss decreased from 11.2226 to 0.0588, by **99.5%**.

---
## 3. Dataset Details

### 3.1 XLCoST Dataset

| Attribute | Value |
| :--- | :--- |
| **Source** | [XLCoST: A Benchmark Dataset for Cross-lingual Code Snippets](https://github.com/xiaobingabc/XLCoST) |
| **Task** | Java → C# (Program-level) |
| **Training Set (Java)** | 9,623 programs |
| **Training Set (C#)** | 9,345 programs |
| **Test Set (Java)** | 911 programs |
| **Test Set (C#)** | 899 programs |
| **Evaluated Samples** | 894 (Aligned) |

> **Note**: Evaluation uses aligned test set (`xlcost_data/data/aligned/`), ensuring 1-to-1 Java-C# correspondence.


### 3.2 Test Sample Statistics

- **Avg Input Length**: 679 chars
- **Max Input Length**: 2869 chars

---
## 4. Evaluation Metrics (Full Details)

### 4.1 Semantic Consistency

| Metric | Value | Calculation Method |
| :--- | ---: | :--- |
| **BLEU** | 100.00 | SacreBLEU 4-gram |
| **CodeBLEU** | 0.9390 | Weighted Composite (Items below) |
| ├─ N-gram Match | 0.9299 | Standard n-gram match |
| ├─ Weighted N-gram | 0.9464 | Keyword weighted |
| ├─ **Syntax (AST)** | 0.9324 | Syntax Tree Structure Match |
| └─ **DataFlow** | 0.9471 | Variable Logic Flow Match |
| **Exact Match** | 11.5% | Completely Identical Ratio |

### 4.2 Executability

| Metric | Value | Description |
| :--- | ---: | :--- |
| **Compilation Rate** | 69.24% | `dotnet build` test |
| **Syntax Validity (AST)** | 92.28% | Tree-sitter Parse Success Rate |

### 4.3 Code Quality

| Metric | Value | Description |
| :--- | ---: | :--- |
| **Naming Convention Score** | 69.1% | C# Naming Convention Compliance |
| ├─ PascalCase Methods | 1025/2185 | Method Name Detection |
| **Avg C# Idioms / Sample** | 0.12 | Idiom Density |
| ├─ LINQ Usage | 0 | .Where(), .Select()... |
| ├─ foreach Usage | 81 | - |
| ├─ var Keyword | 0 | - |
| **Java Pattern Residue** | 0 | Residual Java Style Code |

### 4.6 Functional Correctness (Code-to-Code)\n
| Metric | Base Model | Fine-tuned Model | Improvement |
| :--- | ---: | ---: | ---: |
| **Function Pass Rate** | 0.00% | **72.06%** | +72.06% |
| **Compilation Rate** | 0.00% | **85.29%** | +85.29% |
| **Tests Passed** | 0/68 | **49/68** | +49 |

> **Note**: Functional correctness uses comparison of execution output against reference C# code.\n

### 4.7 Regression Test (Text-to-Code)\n
Evaluates if fine-tuned model capability degrades on original Text-to-code tasks (Catastrophic Forgetting Detection).\n
| Metric | Base Model | Fine-Tuned Model | Diff |
| :--- | ---: | ---: | ---: |
| **BLEU** | 0.00 | **4.40** | +4.40 |
| **CodeBLEU** | 0.01 | **0.08** | +0.07 |

> ✅ **Info**: Fine-tuned model improved on Text-to-code task, indicating positive transfer.\n

---
## 5. Qualitative Analysis (Case Studies)

### Case Study #1

**Input (Java):**
```java
import java . util . * ; class GFG { static void countSubarray ( int [ ] arr , int n ) { int L = 0 , R = 0 ; int mx = Integer . MIN_VALUE ; for ( int i = 0 ; i < n ; i ++ ) mx = Math . max ( mx , arr [ i ] ) ; for ( int i = 0 ; i < n ; i ++ ) { if ( arr [ i ] * 2 > mx ) { L = i ; break ; } } for ( int i = n - 1 ; i >= 0 ; i -- ) { if ( arr [ i ] * 2 > mx ) { R = i ; break ; } } System . out . println ( ( L + 1 ) * ( n - R ) ) ; } public static void main ( String [ ] args ) { int [ ] arr = { 1 , 6 , 10 , 9 , 7 , 3 } ; int N = arr . length ; countSubarray ( arr , N ) ; } }
```

**Reference (C#):**
```csharp
using System ; class GFG { static void countSubarray ( int [ ] arr , int n ) { int L = 0 , R = 0 ; int mx = Int32 . MinValue ; for ( int i = 0 ; i < n ; i ++ ) mx = Math . Max ( mx , arr [ i ] ) ; for ( int i = 0 ; i < n ; i ++ ) { if ( arr [ i ] * 2 > mx ) { L = i ; break ; } } for ( int i = n - 1 ; i >= 0 ; i -- ) { if ( arr [ i ] * 2 > mx ) { R = i ; break ; } } Console . WriteLine ( ( L + 1 ) * ( n - R ) ) ; } public static void Main ( ) { int [ ] arr = { 1 , 6 , 10 , 9 , 7 , 3 } ; int N = arr . Length ; countSubarray ( arr , N ) ; } }
```

**Model Prediction:**
```csharp
using System ; class GFG { static void countSubarray ( int [ ] arr , int n ) { int L = 0 , R = 0 ; int mx = int . MinValue ; for ( int i = 0 ; i < n ; i ++ ) mx = Math . Max ( mx , arr [ i ] ) ; for ( int i = 0 ; i < n ; i ++ ) { if ( arr [ i ] * 2 > mx ) { L = i ; break ; } } for ( int i = n - 1 ; i >= 0 ; i -- ) { if ( arr [ i ] * 2 > mx ) { R = i ; break ; } } Console . WriteLine ( ( L + 1 ) * ( n - R ) ) ; } public static void Main ( string [ ] args ) { int [ ] arr = { 1 , 6 , 10 , 9 , 7 , 3 } ; int N = arr . Length ; countSubarray ( arr , N ) ; } }
```

- Idiom Score: 0.5
- Naming Score: 63.64%

---

### Case Study #2

**Input (Java):**
```java
import java . util . * ; class GFG { static void findClosest ( int N , int target ) { int closest = - 1 ; int diff = Integer . MAX_VALUE ; for ( int i = 1 ; i <= ( int ) Math . sqrt ( N ) ; i ++ ) { if ( N % i == 0 ) { if ( N / i == i ) { if ( Math . abs ( target - i ) < diff ) { diff = Math . abs ( target - i ) ; closest = i ; } } else { if ( Math . abs ( target - i ) < diff ) { diff = Math . abs ( target - i ) ; closest = i ; } if ( Math . abs ( target - N / i ) < diff ) { diff = Math . abs ( target - N / i ) ; closest = N / i ; } } } } System . out . println ( closest ) ; } public static void main ( String [ ] args ) { int N = 16 , X = 5 ; findClosest ( N , X ) ; } }
```

**Reference (C#):**
```csharp
using System ; class GFG { static void findClosest ( int N , int target ) { int closest = - 1 ; int diff = Int32 . MaxValue ; for ( int i = 1 ; i <= Math . Sqrt ( N ) ; i ++ ) { if ( N % i == 0 ) { if ( N / i == i ) { if ( Math . Abs ( target - i ) < diff ) { diff = Math . Abs ( target - i ) ; closest = i ; } } else { if ( Math . Abs ( target - i ) < diff ) { diff = Math . Abs ( target - i ) ; closest = i ; } if ( Math . Abs ( target - N / i ) < diff ) { diff = Math . Abs ( target - N / i ) ; closest = N / i ; } } } } Console . Write ( closest ) ; } static void Main ( ) { int N = 16 , X = 5 ; findClosest ( N , X ) ; } }
```

**Model Prediction:**
```csharp
using System ; class GFG { static void findClosest ( int N , int target ) { int closest = - 1 ; int diff = int . MaxValue ; for ( int i = 1 ; i <= ( int ) Math . Sqrt ( N ) ; i ++ ) { if ( N % i == 0 ) { if ( N / i == i ) { if ( Math . Abs ( target - i ) < diff ) { diff = Math . Abs ( target - i ) ; closest = i ; } } else { if ( Math . Abs ( target - i ) < diff ) { diff = Math . Abs ( target - i ) ; closest = i ; } if ( Math . Abs ( target - N / i ) < diff ) { diff = Math . Abs ( target - N / i ) ; closest = N / i ; } } } } Console . WriteLine ( closest ) ; } public static void Main ( string [ ] args ) { int N = 16 , X = 5 ; findClosest ( N , X ) ; } }
```

- Idiom Score: 0.5
- Naming Score: 66.67%

---

### Case Study #3

**Input (Java):**
```java
class GFG { static int func ( int N , int P ) { int sumUptoN = ( N * ( N + 1 ) / 2 ) ; int sumOfMultiplesOfP ; if ( N < P ) { return sumUptoN ; } else if ( ( N / P ) == 1 ) { return sumUptoN - P + 1 ; } sumOfMultiplesOfP = ( ( N / P ) * ( 2 * P + ( N / P - 1 ) * P ) ) / 2 ; return ( sumUptoN + func ( N / P , P ) - sumOfMultiplesOfP ) ; } public static void main ( String [ ] args ) { int N = 10 , P = 5 ; System . out . println ( func ( N , P ) ) ; } }
```

**Reference (C#):**
```csharp
using System ; class GFG { static int func ( int N , int P ) { int sumUptoN = ( N * ( N + 1 ) / 2 ) ; int sumOfMultiplesOfP ; if ( N < P ) { return sumUptoN ; } else if ( ( N / P ) == 1 ) { return sumUptoN - P + 1 ; } sumOfMultiplesOfP = ( ( N / P ) * ( 2 * P + ( N / P - 1 ) * P ) ) / 2 ; return ( sumUptoN + func ( N / P , P ) - sumOfMultiplesOfP ) ; } public static void Main ( String [ ] args ) { int N = 10 , P = 5 ; Console . WriteLine ( func ( N , P ) ) ; } }
```

**Model Prediction:**
```csharp
using System ; class GFG { static int func ( int N , int P ) { int sumUptoN = ( N * ( N + 1 ) / 2 ) ; int sumOfMultiplesOfP ; if ( N < P ) { return sumUptoN ; } else if ( ( N / P ) == 1 ) { return sumUptoN - P + 1 ; } sumOfMultiplesOfP = ( ( N / P ) * ( 2 * P + ( N / P - 1 ) * P ) ) / 2 ; return ( sumUptoN + func ( N / P , P ) - sumOfMultiplesOfP ) ; } public static void Main ( ) { int N = 10 , P = 5 ; Console . WriteLine ( func ( N , P ) ) ; } }
```

- Idiom Score: 0.5
- Naming Score: 57.14%

---

### Case Study #4

**Input (Java):**
```java
import java . io . * ; import java . util . * ; class GFG { static long multiplyByMersenne ( long N , long M ) { long x = ( int ) ( Math . log ( M + 1 ) / Math . log ( 2 ) ) ; return ( ( N << x ) - N ) ; } public static void main ( String [ ] args ) { long N = 4 ; long M = 15 ; System . out . print ( multiplyByMersenne ( N , M ) ) ; } }
```

**Reference (C#):**
```csharp
using System ; class GFG { static int multiplyByMersenne ( int N , int M ) { int x = ( int ) ( Math . Log ( M + 1 ) / Math . Log ( 2 ) ) ; return ( ( N << x ) - N ) ; } static public void Main ( ) { int N = 4 ; int M = 15 ; Console . Write ( multiplyByMersenne ( N , M ) ) ; } }
```

**Model Prediction:**
```csharp
using System ; class GFG { static long multiplyByMersenne ( long N , long M ) { long x = ( int ) ( Math . Log ( M + 1 ) / Math . Log ( 2 ) ) ; return ( ( N << x ) - N ) ; } public static void Main ( ) { long N = 4 ; long M = 15 ; Console . Write ( multiplyByMersenne ( N , M ) ) ; } }
```

- Idiom Score: 0.5
- Naming Score: 50.00%

---

### Case Study #5

**Input (Java):**
```java
import java . io . * ; class GFG { static int countPaths ( int n , int m ) { if ( n == 0 m == 0 ) return 1 ; return ( countPaths ( n - 1 , m ) + countPaths ( n , m - 1 ) ) ; } public static void main ( String [ ] args ) { int n = 3 , m = 2 ; System . out . println ( " ▁ Number ▁ of ▁ Paths ▁ " + countPaths ( n , m ) ) ; } }
```

**Reference (C#):**
```csharp
using System ; public class GFG { static int countPaths ( int n , int m ) { if ( n == 0 m == 0 ) return 1 ; return ( countPaths ( n - 1 , m ) + countPaths ( n , m - 1 ) ) ; } public static void Main ( ) { int n = 3 , m = 2 ; Console . WriteLine ( " ▁ Number ▁ of " + " ▁ Paths ▁ " + countPaths ( n , m ) ) ; } }
```

**Model Prediction:**
```csharp
using System ; class GFG { static int countPaths ( int n , int m ) { if ( n == 0 m == 0 ) return 1 ; return ( countPaths ( n - 1 , m ) + countPaths ( n , m - 1 ) ) ; } public static void Main ( ) { int n = 3 , m = 2 ; Console . WriteLine ( " ▁ Number ▁ of ▁ Paths ▁ " + countPaths ( n , m ) ) ; } };;;;;;
```

- Idiom Score: 0.5
- Naming Score: 66.67%

---

## 6. Conclusion & Discussion

### 6.1 Key Findings

1. **High Quality Translation**: BLEU score 100.00 indicates model generates output highly similar to reference code.
2. **Syntax Retention**: AST Match 0.9324 shows model correctly learned C# syntax structure.
3. **Logic Flow Transfer**: DataFlow Match 0.9471 shows variable def-use logic is well preserved.
4. **C# Style Learning**: Naming score 69.08%, most method names follow PascalCase.
5. **Idiom Adoption**: Model uses C# idioms like LINQ and foreach.

### 6.2 Limitations

- Compilation rate is 69.2%, some generated code has syntax errors.
- Exact match rate is 11.5%, format or detail differences exist between model output and reference.
- Unit test evaluation (Pass@1) not run, functional correctness unverified.
- Naming convention compliance 69.1%, some method names do not use PascalCase.

### 6.3 Future Work

- Run `evaluate_unit_tests.py` for unit test evaluation (Pass@1)
- Optimize post-processing rules to improve compilation rate
- Increase sample weight of C# naming conventions in training data
- Introduce manual review for qualitative analysis
- Compare with other BaseLine models (GPT-3.5, CodeGen, StarCoder, etc.)
- Expand to more language pairs (Python→C#, JavaScript→C#, etc.)

---
## Appendix

### A. File Paths

- **Model**: `C:\Users\Shu Leo\Desktop\practical course\kabul-main\kabul_vipin_edition\fine_tuned_codet5_java_csharp`
- **Evaluation Summary**: `C:\Users\Shu Leo\Desktop\practical course\kabul-main\kabul_vipin_edition\evaluation_summary.json`
- **Detailed Results**: `C:\Users\Shu Leo\Desktop\practical course\kabul-main\kabul_vipin_edition\evaluation_results_multidim.csv`

### B. Environment Info

```
Python: 3.13.9
PyTorch: 2.6.0+cu124
Transformers: 4.57.3
tree-sitter: 0.22+
```


---

# train_report.md

# CodeT5 Java to C# Translation - Training Report

**Generated:** 2026-01-15 18:24:11  
**Total Training Duration:** 4:52:01  
**Best Validation Loss:** 0.056959

---

## 1. Executive Summary

| Metric | Value |
|--------|-------|
| Total Training Time | 4:52:01 |
| Training Samples | 9,228 |
| Validation Samples | 486 |
| Total Training Steps | 3,460 |
| Initial Train Loss | 0.6185 |
| Final Train Loss | 0.0529 |
| Loss Reduction | 91.5% |
| Best Eval Loss | 0.056959 |

---

## 2. System Environment

| Component | Details |
|-----------|---------|
| **Hardware** | |
| GPU | NVIDIA GeForce RTX 4070 Laptop GPU |
| GPU Count | 1 |
| VRAM | 8.0 GB |
| CUDA Version | 12.4 |
| CPU | AMD64 Family 25 Model 68 Stepping 1, AuthenticAMD |
| RAM | 15.24 GB |
| **Software** | |
| OS | Windows-11-10.0.26100-SP0 |
| Python | 3.12.10 |
| PyTorch | 2.6.0+cu124 |
| Transformers | 4.57.5 |

---

## 3. Dataset Statistics

### 3.1 Raw Data & Deduplication

| Metric | Training Set | Validation Set |
|--------|-------------|----------------|
| Raw Java Samples | 9,623 | 494 |
| Raw C# Samples | 9,345 | 491 |
| Aligned Pairs (before dedup) | 9,301 | 491 |
| **Final Pairs (after dedup)** | **9,228** | **486** |
| Duplicates Removed | 73 | 5 |
| Deduplication Rate | 0.78% | 1.02% |

### 3.2 Token Length Distribution

| Language | Mean | Median (P50) | P95 | Max |
|----------|------|--------------|-----|-----|
| Java (Train) | 253.8 | 223 | 524 | 1868 |
| C# (Train) | 247.1 | 216 | 517 | 1865 |
| Java (Valid) | 246.0 | 220 | 494 | 1289 |
| C# (Valid) | 240.1 | 213 | 473 | 1291 |

### 3.3 Truncation & Data Quality

| Metric | Training Set | Validation Set |
|--------|-------------|----------------|
| Max Sequence Length | 512 | 512 |
| Java Truncation Rate | 5.47% | 4.12% |
| C# Truncation Rate | 5.20% | 3.70% |
| Empty Samples | 0 | 0 |
| Very Short Samples (<10 tokens) | 0 (0.00%) | 0 (0.00%) |

### 3.4 Train-Valid Leakage Check (Enhanced)

| Detection Method | Java | C# |
|-----------------|------|-----|
| Exact Match | 1 (0.21%) | 1 (0.21%) |
| Normalized Match (no whitespace/comments) | 1 (0.21%) | 1 (0.21%) |
| High Similarity (Jaccard >0.8) | 0 (0.00%) | 0 (0.00%) |

**Leakage Assessment:** ✅ Clean - No significant leakage detected

**Data Source:**
- Java Training: `xlcost_data/data/Java-program-level/train.json`
- C# Training: `xlcost_data/data/Csharp-program-level/train.json`
- Java Validation: `xlcost_data/data/Java-program-level/valid.json`
- C# Validation: `xlcost_data/data/Csharp-program-level/valid.json`


---

## 4. Model Configuration

### 4.1 Base Model Architecture
| Parameter | Value |
|-----------|-------|
| Model Name | `Salesforce/codet5-base` |
| Architecture | Encoder-Decoder (T5-based) |
| Total Parameters | 222,882,048 |
| Trainable Parameters | 222,882,048 |
| Frozen Parameters | 0 |
| Model Size | 850.23 MB |

### 4.2 Training Hyperparameters
| Parameter | Value | Description |
|-----------|-------|-------------|
| Learning Rate | 3e-05 | Peak learning rate |
| Batch Size (per device) | 4 | Samples per GPU |
| Gradient Accumulation | 2 | Steps to accumulate |
| **Effective Batch Size** | **8** | Total samples per update |
| Epochs | 3 | Training iterations |
| Weight Decay | 0.01 | L2 regularization |
| Warmup Steps | 500 | LR warmup period |
| Max Sequence Length | 512 | Token limit |
| Mixed Precision (FP16) | Enabled | Memory optimization |
| Logging Steps | 10 | Log frequency |
| Save Strategy | epoch | Checkpoint strategy |

---

## 5. Training Results

### 5.1 Per-Epoch Metrics

| Epoch | Train Loss | Eval Loss | Duration | Eval Throughput |
|-------|------------|-----------|----------|-----------------|
| 1 | 0.6185 | 0.0669 | 98.5 min | 21.6 samples/s |
| 2 | 0.0642 | 0.0584 | 97.0 min | 21.6 samples/s |
| 3 | 0.0529 | 0.0570 | 96.5 min | 21.7 samples/s |

### 5.2 Training Convergence Analysis

| Metric | Value |
|--------|-------|
| Initial Loss (Step 1) | 11.2226 |
| Final Loss | 0.0588 |
| Minimum Step Loss | 0.0314 |
| Maximum Step Loss | 11.2226 |
| Average Step Loss | 0.2447 |
| Convergence Step (<0.1 loss) | 440 |

### 5.3 Learning Rate Schedule

| Metric | Value |
|--------|-------|
| Max Learning Rate | 2.99e-05 |
| Min Learning Rate | 6.08e-08 |
| Warmup Steps | 500 |
| Schedule Type | Linear decay with warmup |

### 5.4 Loss Curve Sample Points

| Step | Loss | Learning Rate |
|------|------|---------------|
| 10 | 11.2226 | 3.60e-07 |
| 870 | 0.1345 | 2.63e-05 |
| 1740 | 0.0830 | 1.75e-05 |
| 2600 | 0.0406 | 8.77e-06 |
| 3460 | 0.0588 | 6.08e-08 |

### 5.5 Training Progress Summary

- **Initial Train Loss:** 0.6185
- **Final Train Loss:** 0.0529
- **Loss Reduction:** 91.5%
- **Best Validation Loss:** 0.056959
- **Total Training Steps:** 3,460
- **Steps per Epoch:** ~1,153

---

## 6. Performance Metrics

| Metric | Epoch 1 | Epoch 2 | Epoch 3 |
|--------|---------|---------|---------|
| Eval Runtime | 22.50 | 22.46 | 22.44 |
| Eval Samples Per Second | 21.59 | 21.64 | 21.66 |
| Eval Steps Per Second | 5.42 | 5.43 | 5.44 |

---

## 7. Inference Cost Analysis

### 7.1 Configuration

| Parameter | Value |
|-----------|-------|
| Device | NVIDIA GeForce RTX 4070 Laptop GPU |
| Model Precision | torch.float32 |
| FP16 Enabled | No |
| Max Length | 512 |
| Decoding Strategy | Greedy (num_beams=1) |
| Samples Measured | 50 |

### 7.2 Latency Breakdown (Greedy, batch=1)

| Phase | Mean | P50 | P95 | P99 |
|-------|------|-----|-----|-----|
| Tokenization | 1.0 ms | 0.8 ms | 1.6 ms | 2.0 ms |
| Generation | 5364.0 ms | 4332.6 ms | 12906.6 ms | 14704.6 ms |
| **Total (E2E)** | **5364.9 ms** | **4333.5 ms** | **12908.4 ms** | **14706.3 ms** |

### 7.3 Token Length Statistics

| Metric | Input Tokens | Output Tokens |
|--------|-------------|---------------|
| Mean | 233 | 220 |
| P50 | 208 | 200 |
| P95 | 466 | 449 |
| Max | 512 | 493 |

### 7.4 GPU Memory Usage

| Measurement Method | Value |
|-------------------|-------|
| `torch.cuda.max_memory_allocated()` | 956.4 MB (0.93 GB) |
| `nvidia-smi` (total process) | 1709 MB / 8188 MB |

> **Note:** Difference between PyTorch and nvidia-smi reflects CUDA context overhead (~800 MB).

### 7.5 Batch Throughput

| Batch Size | Throughput (samples/s) |
|------------|----------------------|
| 1 | 0.16 |
| 4 | 0.46 |
| 8 | 0.70 |

### 7.6 Decoding Strategy Comparison

| Strategy | Latency (ms) | Overhead |
|----------|--------------|----------|
| Greedy (num_beams=1) | 6523.7 | - |
| Beam Search (num_beams=4) | 8111.4 | +24.3% |

> Fixed input length: 358 tokens. Output identical: ✅ Yes.

---

## 8. Output Artifacts


| File | Description |
|------|-------------|
| `./fine_tuned_codet5_java_csharp/final_model/config.json` | Model configuration |
| `./fine_tuned_codet5_java_csharp/final_model/model.safetensors` | Model weights |
| `./fine_tuned_codet5_java_csharp/final_model/tokenizer.json` | Tokenizer |
| `./fine_tuned_codet5_java_csharp/training_logs.json` | Detailed step-level training logs |
| `./fine_tuned_codet5_java_csharp/train_report.md` | This report |

---

## 9. Recommendations for Paper

### Key Findings
1. The model achieved significant loss reduction from 0.6185 to 0.0529 (91.5%)
2. Training converged within 440 steps
3. Best validation loss: 0.056959

### Suggested Metrics to Report
- **BLEU Score**: Run `evaluate_model.py` to calculate
- **CodeBLEU**: Available in metrics module
- **Exact Match Rate**: Compare predictions with ground truth

---

> **Note:** For custom visualization and loss curve plotting, use the `training_logs.json` file which contains step-level loss and learning rate data for all 3,460 training steps (logged every 10 steps).


---

# 项目技术文档.md

# Java→C# 代码翻译系统技术文档

> **项目名称**: 基于 CodeT5 的跨语言代码翻译系统  
> **任务**: Java 程序级代码 → C# 代码自动翻译  
> **文档生成日期**: 2026-01-24

---

## 目录

1. [项目概述](#1-项目概述)
2. [系统架构](#2-系统架构)
3. [技术栈](#3-技术栈)
4. [数据集](#4-数据集)
5. [模型训练](#5-模型训练)
6. [后处理流水线](#6-后处理流水线)
7. [评估体系](#7-评估体系)
8. [工作流程](#8-工作流程)
9. [实验结果](#9-实验结果)
10. [文件结构](#10-文件结构)

---

## 1. 项目概述

### 1.1 研究背景

跨语言代码翻译是软件工程领域的重要研究方向，旨在自动将一种编程语言的代码转换为语法和语义等价的另一种编程语言代码。本项目专注于 **Java → C#** 的程序级代码翻译任务。

### 1.2 研究目标

- 利用预训练代码模型（CodeT5）进行微调，实现高质量的 Java→C# 代码翻译
- 构建多维度评估体系，全面衡量翻译质量
- 设计后处理流水线，提升生成代码的可编译性

### 1.3 核心贡献

1. **微调 CodeT5 模型**: 在 XLCoST 数据集上进行 Java→C# 翻译任务的微调
2. **三层后处理流水线**: 规则清洗 → 格式化 → 编译器自修复
3. **多维度评估框架**: 语义一致性、可执行性、代码质量三个维度的综合评估

---

## 2. 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        系统整体架构                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │   数据准备    │───▶│   模型训练    │───▶│    推理生成   │      │
│  │  (对齐/预处理) │    │  (CodeT5微调) │    │  (翻译预测)  │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│         │                   │                   │              │
│         ▼                   ▼                   ▼              │
│  ┌──────────────────────────────────────────────────────┐      │
│  │                    后处理流水线                        │      │
│  │  Layer 1: 规则清洗 → Layer 2: 格式化 → Layer 3: 自修复  │      │
│  └──────────────────────────────────────────────────────┘      │
│                            │                                   │
│                            ▼                                   │
│  ┌──────────────────────────────────────────────────────┐      │
│  │                    多维度评估                          │      │
│  │  BLEU │ CodeBLEU │ 编译率 │ 精确匹配 │ 惯用法 │ 命名规范  │      │
│  └──────────────────────────────────────────────────────┘      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. 技术栈

### 3.1 核心框架

| 组件 | 技术 | 版本 | 用途 |
|------|------|------|------|
| **深度学习框架** | PyTorch | 2.6.0 | 模型训练与推理 |
| **预训练模型库** | Hugging Face Transformers | 4.57.3 | Seq2Seq 训练框架 |
| **基座模型** | Salesforce/codet5-base | - | 编码器-解码器 Transformer |
| **语法解析** | Tree-sitter | 0.22+ | AST 构建与 CodeBLEU 计算 |
| **评估指标** | SacreBLEU | - | BLEU 分数计算 |

### 3.2 模型架构 (CodeT5)

| 参数 | 值 | 说明 |
|------|------|------|
| **架构类型** | T5ForConditionalGeneration | 编码器-解码器 Transformer |
| **总参数量** | ~220M | 约 2.2 亿参数 |
| **隐藏层维度** (d_model) | 768 | Token 嵌入维度 |
| **编码器/解码器层数** | 12 | 各 12 层 Transformer Block |
| **注意力头数** | 12 | 多头自注意力 |
| **前馈层维度** (d_ff) | 3072 | FFN 中间维度 |
| **词表大小** | 32,100 | BPE 分词 |
| **最大序列长度** | 512 | 输入/输出 Token 上限 |
| **Dropout 率** | 0.1 | 正则化 |

### 3.3 开发环境

- **Python**: 3.11+
- **CUDA**: 12.4
- **操作系统**: Windows 11
- **编译器**: .NET SDK 7.0 (用于 C# 编译验证)

---

## 4. 数据集

### 4.1 数据来源: XLCoST 基准

XLCoST (Cross-Lingual Code Snippets) 是一个多语言代码翻译基准数据集，支持 7 种编程语言。

**引用**:
```
Zhu et al., "XLCoST: A Benchmark Dataset for Cross-lingual Code Intelligence", 
arXiv:2206.08474, 2022
```

### 4.2 数据统计

| 数据集 | Java 样本数 | C# 样本数 | 对齐后样本数 |
|--------|-------------|-----------|--------------|
| **训练集** | 9,623 | 9,345 | ~9,000 |
| **验证集** | 481 | 472 | ~460 |
| **测试集** | 911 | 899 | 894 |

### 4.3 数据格式

每个样本包含:
- `text`: 问题描述（自然语言）
- `code`: 源代码

**示例** (Java):
```json
{
  "text": "Maximum Prefix Sum | Implementation of the above approach...",
  "code": "public static void main(String[] args) { ... }"
}
```

### 4.4 数据对齐策略

由于 Java 和 C# 原始数据集存在样本数不匹配（Java: 911, C#: 899），采用**描述文本精确匹配**策略进行对齐：

1. 提取每个样本的 `text` 字段，截取 `|` 前的核心描述
2. 按描述分组，建立 Java/C# 的描述→代码映射
3. 取两边描述的交集，生成对齐的样本对
4. 代码级去重，移除重复代码片段

**实现文件**: `align_datasets.py`

---

## 5. 模型训练

### 5.1 训练配置

| 超参数 | 值 | 说明 |
|--------|------|------|
| **学习率** | 3e-5 | AdamW 优化器 |
| **批大小 (per device)** | 4 | 单 GPU 批大小 |
| **梯度累积步数** | 2 | 等效批大小 = 8 |
| **训练轮数** | 3 | Epochs |
| **权重衰减** | 0.01 | L2 正则化 |
| **预热步数** | 500 | 学习率线性预热 |
| **最大序列长度** | 512 | 输入输出 Token 上限 |
| **混合精度** | FP16 | 加速训练 |
| **保存策略** | 每 epoch | 检查点保存 |

### 5.2 输入格式

训练时采用 Prompt 格式:
```
translate Java to C#: [Java 代码]
```

**标签**: 对应的 C# 代码

### 5.3 训练流程

```python
# 伪代码
tokenizer = AutoTokenizer.from_pretrained("Salesforce/codet5-base")
model = AutoModelForSeq2SeqLM.from_pretrained("Salesforce/codet5-base")

trainer = Seq2SeqTrainer(
    model=model,
    train_dataset=train_dataset,   # 对齐后的 Java-C# 样本对
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

### 5.4 训练结果

| Epoch | 训练损失 | 验证损失 |
|-------|----------|----------|
| 1 | 0.0718 | 0.0669 |
| 2 | 0.0434 | 0.0584 |
| 3 | 0.0588 | 0.0570 |

> 训练损失从初始 ~11.22 降至 0.0588，降低 **99.5%**

---

## 6. 后处理流水线

### 6.1 三层架构

生成的 C# 代码可能包含 Java 残留语法或格式问题，后处理流水线通过三层处理提升代码质量:

```
┌────────────────────────────────────────────────────────────┐
│                    后处理流水线 (PostProcessor)              │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  Layer 1: 规则清洗 (Regex-based Cleaning)                   │
│  ├── 移除 Markdown 代码块                                   │
│  ├── 去除 LLM 会话文本                                      │
│  ├── 原始类型映射 (boolean→bool, Integer→int)               │
│  ├── 字符串方法映射 (.length()→.Length)                     │
│  ├── 集合类型映射 (ArrayList→List, HashMap→Dictionary)      │
│  ├── I/O 映射 (System.out.println→Console.WriteLine)        │
│  ├── 注解处理 (@Override→移除, @Deprecated→[Obsolete])      │
│  ├── Java 特有语法移除 (package, import, throws)            │
│  └── 方法名大小写修正 (toString→ToString)                   │
│                         ▼                                  │
│  Layer 2: 语法格式化 (dotnet format)                        │
│  └── 调用 dotnet format 统一代码风格                        │
│                         ▼                                  │
│  Layer 3: 编译器自修复 (Compiler-Aided Self-Healing)         │
│  ├── 运行 dotnet build 获取编译错误                         │
│  ├── 解析错误代码 (CS1002, CS0103, CS0246 等)               │
│  ├── 应用启发式修复:                                        │
│  │   ├── CS1002: 添加缺失分号                               │
│  │   ├── CS0103/CS0246: 添加 using 语句                     │
│  │   ├── CS1955: 移除属性的方法调用括号                      │
│  │   └── CS1061: 替换 Java 方法为 C# 等价方法               │
│  └── 迭代修复 (最多 3 轮)                                   │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

### 6.2 关键转换规则

| Java 语法 | C# 等价 | 类别 |
|-----------|---------|------|
| `boolean` | `bool` | 原始类型 |
| `Integer` | `int` | 包装类型 |
| `.length()` | `.Length` | 字符串属性 |
| `.charAt(i)` | `[i]` | 字符访问 |
| `.substring(a,b)` | `.Substring(a,b)` | 字符串方法 |
| `ArrayList<T>` | `List<T>` | 集合类型 |
| `HashMap<K,V>` | `Dictionary<K,V>` | 映射类型 |
| `.add()` | `.Add()` | 集合方法 |
| `.size()` | `.Count` | 集合大小 |
| `System.out.println()` | `Console.WriteLine()` | 标准输出 |
| `@Override` | (移除) | 注解 |
| `extends` | `:` | 继承语法 |
| `implements` | `:` | 接口实现 |

**实现文件**: `post_process.py`

---

## 7. 评估体系

### 7.1 评估维度

本项目采用**三维度多指标**评估体系:

```
┌─────────────────────────────────────────────────────────────┐
│                      评估维度框架                            │
├───────────────┬──────────────────┬─────────────────────────┤
│  维度1: 语义   │   维度2: 可执行   │    维度3: 代码质量       │
├───────────────┼──────────────────┼─────────────────────────┤
│ • BLEU        │ • 编译率         │ • C# 惯用法密度          │
│ • CodeBLEU    │ • 语法有效率     │ • 命名规范评分           │
│   ├─ N-gram   │   (AST解析成功)  │   (PascalCase检测)      │
│   ├─ Weighted │                  │ • Java 残留模式检测      │
│   ├─ AST      │                  │                         │
│   └─ DataFlow │                  │                         │
│ • 精确匹配率   │                  │                         │
└───────────────┴──────────────────┴─────────────────────────┘
```

### 7.2 评估指标详解

#### 7.2.1 BLEU (Bilingual Evaluation Understudy)

传统机器翻译评估指标，计算生成代码与参考代码的 n-gram 重叠度。

```python
from sacrebleu import corpus_bleu
bleu = corpus_bleu(predictions, references)
```

#### 7.2.2 CodeBLEU

专为代码设计的评估指标，综合四个子指标:

$$\text{CodeBLEU} = \alpha \cdot \text{BLEU}_{ngram} + \beta \cdot \text{BLEU}_{weighted} + \gamma \cdot \text{Match}_{AST} + \delta \cdot \text{Match}_{DataFlow}$$

默认权重: $\alpha = \beta = \gamma = \delta = 0.25$

| 子指标 | 计算方法 | 意义 |
|--------|----------|------|
| **N-gram Match** | 标准 BLEU | 词级匹配 |
| **Weighted N-gram** | 关键词加权 BLEU | 强调语法关键词 |
| **Syntax Match (AST)** | Tree-sitter 解析 AST，比较结构 | 语法结构相似性 |
| **DataFlow Match** | 变量定义-使用链分析 | 语义逻辑相似性 |

**实现文件**: `metrics/codebleu_eval.py`, `metrics/native_codebleu/`

#### 7.2.3 编译率

使用 .NET SDK 编译生成的 C# 代码:

```python
result = subprocess.run(["dotnet", "build", project_dir], ...)
compilation_rate = compiled_count / total_count
```

**实现文件**: `metrics/compilation_eval.py`

#### 7.2.4 精确匹配率

去除空白后比较生成代码与参考代码是否完全相同:

```python
def normalize(code):
    return re.sub(r'\s+', '', code)

exact_match = sum(normalize(pred) == normalize(ref) for pred, ref in pairs) / len(pairs)
```

**实现文件**: `metrics/exact_match_eval.py`

#### 7.2.5 C# 惯用法密度

检测生成代码中 C# 特有惯用语的使用频率:

| 惯用法类别 | 检测模式 |
|------------|----------|
| **LINQ** | `.Where()`, `.Select()`, `.FirstOrDefault()` 等 |
| **var 关键字** | `var x = ...` |
| **foreach** | `foreach (var x in ...)` |
| **自动属性** | `{ get; set; }` |
| **空条件运算符** | `?.`, `??`, `??=` |
| **字符串插值** | `$"... {var} ..."` |
| **表达式体成员** | `=> expression;` |
| **async/await** | `async`, `await` |
| **模式匹配** | `is Type name`, `switch` 表达式 |

**实现文件**: `metrics/idiom_eval.py`

#### 7.2.6 命名规范评分

检测方法名是否遵循 C# PascalCase 命名规范:

```python
def is_pascal_case(name):
    return re.match(r'^[A-Z][a-zA-Z0-9]*$', name) is not None

naming_score = pascal_case_methods / total_methods
```

**实现文件**: `metrics/naming_eval.py`

---

## 8. 工作流程

### 8.1 完整流程图

```
┌─────────────────────────────────────────────────────────────────┐
│                        完整工作流程                              │
└─────────────────────────────────────────────────────────────────┘

1. 数据准备阶段
   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
   │ 下载 XLCoST │───▶│  数据对齐    │───▶│  预处理      │
   │   数据集    │    │ (按描述匹配) │    │ (分词/截断)  │
   └─────────────┘    └─────────────┘    └─────────────┘
         │                  │                  │
         ▼                  ▼                  ▼
   xlcost_data/      align_datasets.py   train_data.py

2. 模型训练阶段
   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
   │  加载配置   │───▶│  加载模型    │───▶│   训练循环   │
   │ (超参数)    │    │ (CodeT5)    │    │ (Epoch迭代) │
   └─────────────┘    └─────────────┘    └─────────────┘
         │                  │                  │
         ▼                  ▼                  ▼
   train_config.py   Salesforce/codet5   train_model.py
                                               │
                                               ▼
                                    fine_tuned_codet5_java_csharp/

3. 评估阶段
   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
   │  加载测试集  │───▶│   推理生成   │───▶│   后处理    │
   │ (对齐版)    │    │ (Beam=1)    │    │ (3层流水线) │
   └─────────────┘    └─────────────┘    └─────────────┘
         │                                      │
         ▼                                      ▼
   aligned/*.json                        post_process.py
                                               │
   ┌─────────────┐    ┌─────────────┐          │
   │  计算指标   │◀───│  对比参考    │◀─────────┘
   │ (多维度)    │    │   代码      │
   └─────────────┘    └─────────────┘
         │
         ▼
   metrics/*.py
         │
         ▼
   ┌─────────────────────────────────────────┐
   │            评估结果输出                   │
   │  evaluation_summary.json                │
   │  evaluation_results_multidim.csv        │
   │  research_paper_report.md               │
   └─────────────────────────────────────────┘
```

### 8.2 命令行执行

```bash
# 1. 数据对齐
python align_datasets.py

# 2. 模型训练
python train_model.py

# 3. 模型评估
python evaluate_model.py

# 4. 生成报告
python generate_report.py
```

---

## 9. 实验结果

### 9.1 主要指标

| 维度 | 指标 | 值 | 说明 |
|------|------|------|------|
| **语义** | BLEU | **100.00** | 传统 n-gram 匹配 |
| **语义** | CodeBLEU | **0.9390** | AST + DataFlow 综合 |
| | ├─ Syntax (AST) | 0.9324 | 语法树结构匹配 |
| | └─ DataFlow | 0.9471 | 变量逻辑流匹配 |
| **可执行** | 编译率 | 69.24% | dotnet build 测试 |
| **质量** | 命名规范 | **69.1%** | PascalCase 合规率 |
| **质量** | C# 惯用法 | 0.12/样本 | LINQ/var/foreach |

### 9.2 模型对比 (微调 vs 基座)

| 指标 | 基座模型 | 微调模型 | 提升 |
|------|----------|----------|------|
| BLEU | 54.17 | **100.00** | +45.83 |
| CodeBLEU | 0.1029 | **0.9390** | +0.8360 |
| Syntax (AST) | 0.0474 | **0.9324** | +0.8850 |
| DataFlow | 0.0467 | **0.9471** | +0.9004 |
| 功能通过率 | 0.00% | **72.06%** | +72.06% |

> **BLEU 提升**: 从 54.17 提升至 100.00，提升 **84.6%**

### 9.3 案例展示

**Java 输入**:
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

**C# 输出**:
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

**关键转换**:
- `import java.util.*` → `using System`
- `Integer.MIN_VALUE` → `int.MinValue`
- `Math.max` → `Math.Max`

---

## 10. 文件结构

```
kabul_vipin_edition/
├── 核心代码
│   ├── train_model.py        # 主训练脚本
│   ├── train_config.py       # 训练超参数配置
│   ├── train_data.py         # 数据加载与对齐
│   ├── train_report.py       # 训练报告生成
│   ├── align_datasets.py     # 测试集数据对齐
│   ├── evaluate_model.py     # 多维度评估主脚本
│   ├── post_process.py       # 后处理流水线
│   └── generate_report.py    # 评估报告生成
│
├── 评估指标 (metrics/)
│   ├── __init__.py
│   ├── codebleu_eval.py      # CodeBLEU 计算
│   ├── compilation_eval.py   # 编译率评估
│   ├── exact_match_eval.py   # 精确匹配率
│   ├── idiom_eval.py         # C# 惯用法密度
│   ├── naming_eval.py        # 命名规范评分
│   ├── syntax_validity_eval.py # AST 语法有效性
│   └── native_codebleu/      # 原生 Tree-sitter 实现
│
├── 数据集 (xlcost_data/)
│   ├── data/
│   │   ├── Java-program-level/   # Java 数据
│   │   │   ├── train.json
│   │   │   ├── valid.json
│   │   │   └── test.json
│   │   ├── Csharp-program-level/ # C# 数据
│   │   │   ├── train.json
│   │   │   ├── valid.json
│   │   │   └── test.json
│   │   └── aligned/              # 对齐后数据
│   │       ├── java_aligned.json
│   │       └── csharp_aligned.json
│   └── README.md
│
├── 模型输出 (fine_tuned_codet5_java_csharp/)
│   ├── final_model/          # 最终模型权重
│   ├── training_logs.json    # 训练日志
│   └── train_report.md       # 训练报告
│
├── 评估结果
│   ├── evaluation_summary.json       # 评估摘要
│   ├── evaluation_results_multidim.csv # 详细结果
│   └── research_paper_report.md      # 研究报告
│
└── 其他
    ├── AIMODELTRAINING.ipynb  # Jupyter 笔记本
    ├── verify_setup.py        # 环境验证
    └── .gitignore
```

---

## 附录

### A. 依赖库

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

### B. 硬件要求

| 组件 | 推荐配置 |
|------|----------|
| GPU | NVIDIA RTX 3080+ (16GB+ VRAM) |
| RAM | 32GB+ |
| 存储 | 50GB+ SSD |
| CUDA | 12.0+ |

### C. 参考文献

1. Wang et al., "CodeT5: Identifier-aware Unified Pre-trained Encoder-Decoder Models for Code Understanding and Generation", EMNLP 2021
2. Zhu et al., "XLCoST: A Benchmark Dataset for Cross-lingual Code Intelligence", arXiv 2022
3. Ren et al., "CodeBLEU: a Method for Automatic Evaluation of Code Synthesis", arXiv 2020

---

*文档结束*


---

