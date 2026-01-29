# Evaluation Report

*Generated: 2026-01-29 00:52:07*


## ① Overview

| Field | Value |
|-------|-------|
| Model | deepseek-coder-6.7b-instruct |
| Dataset | test_split.jsonl (200 problems) |
| num_samples | 10 |
| temperature | 0.2 |
| seed | 42 |
| Eval Run ID | `eval_run_2026_01_22_215157` |
| Date | 2026-01-22 |

## ② Core Metrics

| Metric | Value |
|--------|-------|
| **Pass@1** | 56.40% |
| Pass@5 | 65.04% |
| Pass@10 | 67.00% |
| Compile Rate | 98.70% |
| Avg Runtime | 54.3ms |
| P50 Runtime | 48.1ms |
| P95 Runtime | 97.1ms |
| Max Runtime | 1186.0ms |

## ③ Error Analysis

| Error Type | Rate |
|------------|------|
| SyntaxError | 1.30% |
| RuntimeError | 10.95% |
| Timeout | 0.00% |
| AssertionError (WA) | 31.35% |
| ImportError | 0.00% |
| MemoryError | 0.00% |

## ④ Code Quality

| Metric | Value |
|--------|-------|
| Interface Compliance | 100.0% |
| Extra I/O Rate | 0.4% |
| Avg Code Length | 130 chars |
| Avg Lines | 4.7 |

> **📌 About Extra I/O Rate**
> 
> - `print()` statements: **Do not affect test results** (tests check return values, not stdout)
> - `input()` statements: **Cause Timeout (TLE)** (code blocks waiting for stdin)
> - **High Extra I/O Rate** indicates the model's training data is biased towards competitive programming I/O style.
> - **Recommendation**: Consider prompt engineering or data cleaning to reduce I/O patterns.

## ⑤ Segment Analysis

### By Difficulty

| Difficulty | Pass@1 | Compile Rate |
|------------|--------|--------------|
| unknown | 56.4% | 98.7% |

### Per-Problem Pass Rate Distribution

> Measures variance across problems - high std indicates uneven difficulty handling

| Statistic | Value |
|-----------|-------|
| Min | 0.0% |
| Median | 80.0% |
| Mean | 56.4% |
| Max | 100.0% |
| Std Dev | 45.4% |
| Total Problems | 2000 |

## ⑥ Failure Case Examples (by Error Type)

> Diverse sampling: different tasks selected to show variety of failures

### 🔴 SyntaxError

**Example 1**: Task `train_final_00735` (Difficulty: unknown)
- **Prompt**:
> Write a function to convert rgb color to hsv color.
- **Error**:
````
Line 3: invalid syntax
````
- **Generated Output** (LLM raw response):
````
def rgb_to_hsv(r,g,b):
    maxc = max(r, g, b); minc = min(r, g, b)
    v = maxc; if minc == maxc: return 0.
    s = (maxc-minc) / maxc
    rc = (maxc-r) / (maxc-minc)
    gc = (maxc-g) / (maxc-minc)
    bc = (maxc-b) / (maxc-minc)
    if r == maxc: h = 60 * (bc-gc)
    elif g == maxc: h = 120 + 60 * (rc-bc)
    else: h = 240 + 60 * (gc-rc)
    if h < 0: h += 360
    return round(h), round(s*100), round(v*100)

````

**Example 2**: Task `train_final_00083` (Difficulty: unknown)
- **Prompt**:
> Write a function to merge three dictionaries into a single expression.
- **Error**:
````
Line 2: invalid syntax
````
- **Generated Output** (LLM raw response):
````
def merge_dictionaries_three(dict1, dict2, dict3):
    return {**dict1, **dict2, **dict3}

````

**Example 3**: Task `train_final_01207` (Difficulty: unknown)
- **Prompt**:
> Write a function to find the greatest common divisor (GCD) of a list of numbers.
- **Error**:
````
Line 6: expected an indented block after 'for' statement on line 5
````
- **Generated Output** (LLM raw response):
````
from math import gcd
def find_gcd_list(nums): 
    num1 = nums[0] 
    num2 = nums[1] 
    result = gcd(num1, num2) 
    for i in range(2, len(nums)): 
        result = gcd(result, nums[i]) 
    return result

````

### 🟠 RuntimeError

**Example 1**: Task `train_final_00083` (Difficulty: unknown)
- **Prompt**:
> Write a function to merge three dictionaries into a single expression.
- **Error**:
````
Traceback (most recent call last):
  File "C:\Users\SHULEO~1\AppData\Local\Temp\tmpk3xrvv4b.py", line 10, in <module>
    test_solve()
  File "C:\Users\SHULEO~1\AppData\Local\Temp\tmpk3xrvv4b.py", line 5, in test_solve
    assert merge_dictionaries_three({ "R": "Red", "B": "Black", "P": "Pink" }, { "G": "Green", "W": "White" },{ "O": "Orange", "W": "White", "B": "Black" })=={'B': 'Black', 'R': 'Red', 'P': 'Pink', 'G': 'Green', 'W': 'White', 'O': 'Orange'}
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
````
- **Generated Output** (LLM raw response):
````
def merge_dictionaries_three(dict1, dict2, dict3):
    result = {**dict1, **dict2, **dict3}
    return result

````

**Example 2**: Task `train_final_00847` (Difficulty: unknown)
- **Prompt**:
> Write a python function to find the sum of squares of binomial co-efficients.
- **Error**:
````
Traceback (most recent call last):
  File "C:\Users\SHULEO~1\AppData\Local\Temp\tmp01xgwwvb.py", line 13, in <module>
    test_solve()
  File "C:\Users\SHULEO~1\AppData\Local\Temp\tmp01xgwwvb.py", line 8, in test_solve
    assert sum_of_square(4) == 70
           ^^^^^^^^^^^^^
NameError: name 'sum_of_square' is not defined

````
- **Generated Output** (LLM raw response):
````
def factorial(start,end):
    fact=1
    for i in range(start+1,end+1):
        fact*=i
    return fact

````

**Example 3**: Task `train_final_00708` (Difficulty: unknown)
- **Prompt**:
> Write a function to find common index elements from three lists.
- **Error**:
````
Traceback (most recent call last):
  File "C:\Users\SHULEO~1\AppData\Local\Temp\tmp0fjajrdh.py", line 10, in <module>
    test_solve()
  File "C:\Users\SHULEO~1\AppData\Local\Temp\tmp0fjajrdh.py", line 5, in test_solve
    assert extract_index_list([1, 1, 3, 4, 5, 6, 7],[0, 1, 2, 3, 4, 5, 7],[0, 1, 2, 3, 4, 5, 7])==[1, 7]
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\SHULEO~1\AppData\Local\Temp\tmp0fjajrdh.py", line 2, in extrac
````
- **Generated Output** (LLM raw response):
````
def extract_index_list(l1, l2, l3):
    result = [i for i in range(len(l1)) if l1[i] == l2[i] == l3[i]]
    return result

````

### 🟡 AssertionError (WA)

**Example 1**: Task `train_final_00843` (Difficulty: unknown)
- **Prompt**:
> Write a function where a string will start with a specific number.
- **Error**:
````
Traceback (most recent call last):
  File "C:\Users\SHULEO~1\AppData\Local\Temp\tmpq2fn_vdw.py", line 15, in <module>
    test_solve()
  File "C:\Users\SHULEO~1\AppData\Local\Temp\tmpq2fn_vdw.py", line 11, in test_solve
    assert match_num('6-2345861')==False
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError

````
- **Generated Output** (LLM raw response):
````
import re
def match_num(text):
  pattern = '^[0-9]'
  if re.search(pattern, text):
    return True
  else:
    return False

````

**Example 2**: Task `train_final_00580` (Difficulty: unknown)
- **Prompt**:
> Write a function to perfom the modulo of tuple elements in the given two tuples.
- **Error**:
````
Traceback (most recent call last):
  File "C:\Users\SHULEO~1\AppData\Local\Temp\tmp2evvn7t5.py", line 14, in <module>
    test_solve()
  File "C:\Users\SHULEO~1\AppData\Local\Temp\tmp2evvn7t5.py", line 9, in test_solve
    assert tuple_modulo((10, 4, 5, 6), (5, 6, 7, 5)) == (0, 4, 5, 1)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError

````
- **Generated Output** (LLM raw response):
````
def tuple_modulo(test_tup1, test_tup2):
  res = []
  for ele1, ele2 in zip(test_tup1, test_tup2):
    if isinstance(ele1, int) and isinstance(ele2, int):
      res.append((ele1 % ele2))
  return (res)

````

**Example 3**: Task `train_final_00668` (Difficulty: unknown)
- **Prompt**:
> Write a function to check if the given tuple contains all valid values or not.
- **Error**:
````
Traceback (most recent call last):
  File "C:\Users\SHULEO~1\AppData\Local\Temp\tmp896nr007.py", line 11, in <module>
    test_solve()
  File "C:\Users\SHULEO~1\AppData\Local\Temp\tmp896nr007.py", line 7, in test_solve
    assert check_valid((True, False, True, True) ) == False
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError

````
- **Generated Output** (LLM raw response):
````
def check_valid(test_tup):
  res = all((isinstance(ele, int) for ele in test_tup))
  return (res)

````

## ⑦ Evaluation Protocol

### Generation Settings
- **Samples per task**: 10
- **Temperature**: 0.2
- **Selection**: First k samples in generation order (not best-of-k)

### Pass@k Definition
- A task passes at k if **at least one** of the first k samples passes **all** test cases
- Using unbiased estimator: `pass@k = 1 - C(n-c,k)/C(n,k)` where n=samples, c=correct

### Judge Settings
- **Timeout**: 6s per test case
- **Sandbox**: subprocess isolation, no network/file access
- **Compile Rate**: Percentage of samples that run without SyntaxError
