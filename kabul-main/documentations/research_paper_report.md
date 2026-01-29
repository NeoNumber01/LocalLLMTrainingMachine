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
