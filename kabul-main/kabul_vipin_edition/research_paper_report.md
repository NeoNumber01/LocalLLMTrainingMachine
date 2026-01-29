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
