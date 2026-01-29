# Evaluation Report

*Generated: 2026-01-29 00:56:36*


## ① Overview

| Field | Value |
|-------|-------|
| Model | deepseek-coder-6.7b-instruct |
| Dataset | test_split.jsonl (200 problems) |
| num_samples | 10 |
| temperature | 0.2 |
| seed | 42 |
| Eval Run ID | `eval_run_2026_01_23_162339` |
| Date | 2026-01-23 |

## ② Core Metrics

| Metric | Value |
|--------|-------|
| **Pass@1** | 57.00% |
| Pass@5 | 64.53% |
| Pass@10 | 65.50% |
| Compile Rate | 99.15% |
| Avg Runtime | 52.1ms |
| P50 Runtime | 45.5ms |
| P95 Runtime | 109.3ms |
| Max Runtime | 1249.6ms |

## ③ Error Analysis

| Error Type | Rate |
|------------|------|
| SyntaxError | 0.85% |
| RuntimeError | 11.10% |
| Timeout | 0.00% |
| AssertionError (WA) | 31.05% |
| ImportError | 0.00% |
| MemoryError | 0.00% |

## ④ Code Quality

| Metric | Value |
|--------|-------|
| Interface Compliance | 100.0% |
| Extra I/O Rate | 0.3% |
| Avg Code Length | 129 chars |
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
| unknown | 57.0% | 99.2% |

### Per-Problem Pass Rate Distribution

> Measures variance across problems - high std indicates uneven difficulty handling

| Statistic | Value |
|-----------|-------|
| Min | 0.0% |
| Median | 80.0% |
| Mean | 57.0% |
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
  maxc = max(r,g,b); minc = min(r,g,b)
  v = maxc; if minc == maxc: return 0., 0., v
  s = (maxc-minc) / maxc; l = (maxc+minc)/2.0
  if s == 0.0: return 0.0, 0.0, l
  if l < 0.5: m = (maxc+minc)/2.0
  else: m = (maxc+minc)/2.0
  if maxc == r: h = 60 * ((g-b)/(maxc-minc)) % 360
  elif maxc == g: h = 60 * ((b-r)/(maxc-minc)) + 120
  elif maxc == b: h = 60 * ((r-g)/(maxc-minc)) + 240
  return round(h), round(s*100), round(v)

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

**Example 1**: Task `train_final_00847` (Difficulty: unknown)
- **Prompt**:
> Write a python function to find the sum of squares of binomial co-efficients.
- **Error**:
````
Traceback (most recent call last):
  File "C:\Users\SHULEO~1\AppData\Local\Temp\tmpkkj4u6s9.py", line 21, in <module>
    test_solve()
  File "C:\Users\SHULEO~1\AppData\Local\Temp\tmpkkj4u6s9.py", line 16, in test_solve
    assert sum_of_square(4) == 70
           ^^^^^^^^^^^^^
NameError: name 'sum_of_square' is not defined

````
- **Generated Output** (LLM raw response):
````
def factorial(n):
    if n==0 or n==1: return 1
    else: return n*factorial(n-1)
def bin_coeff(x,y):
    res = 1
    for i in range(0, y+1):
        res = res * (x - i + 1) / (i)
    return res
def sum_sqr_binomial(n):
    s=0
    for k in range(2,n//2+1):
        s += (bin_coeff(n,k))**2
    return s

````

**Example 2**: Task `train_final_00083` (Difficulty: unknown)
- **Prompt**:
> Write a function to merge three dictionaries into a single expression.
- **Error**:
````
Traceback (most recent call last):
  File "C:\Users\SHULEO~1\AppData\Local\Temp\tmpe42gef_1.py", line 10, in <module>
    test_solve()
  File "C:\Users\SHULEO~1\AppData\Local\Temp\tmpe42gef_1.py", line 5, in test_solve
    assert merge_dictionaries_three({ "R": "Red", "B": "Black", "P": "Pink" }, { "G": "Green", "W": "White" },{ "O": "Orange", "W": "White", "B": "Black" })=={'B': 'Black', 'R': 'Red', 'P': 'Pink', 'G': 'Green', 'W': 'White', 'O': 'Orange'}
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
````
- **Generated Output** (LLM raw response):
````
def merge_dictionaries_three(dict1, dict2, dict3):
    result = {**dict1, **dict2, **dict3}
    return result

````

**Example 3**: Task `train_final_00027` (Difficulty: unknown)
- **Prompt**:
> Write a python function to find binomial co-efficient.
- **Error**:
````
Traceback (most recent call last):
  File "C:\Users\SHULEO~1\AppData\Local\Temp\tmp_a8sehtl.py", line 17, in <module>
    test_solve()
  File "C:\Users\SHULEO~1\AppData\Local\Temp\tmp_a8sehtl.py", line 12, in test_solve
    assert binomial_Coeff(5,2) == 10
           ^^^^^^^^^^^^^^^^^^^
  File "C:\Users\SHULEO~1\AppData\Local\Temp\tmp_a8sehtl.py", line 2, in binomial_Coeff
    C = [[0 for x in range(K+1)]for y in range(n+1)]
                           ^
NameError: name 'K' is not defined. Did yo
````
- **Generated Output** (LLM raw response):
````
def binomial_Coeff(n,k): 
    C = [[0 for x in range(K+1)]for y in range(n+1)] 
    for i in range(n + 1): 
        for j in range(min(i, k) + 1): 
            if (j == 0 or j == i): 
                C[i][j] = 1
            else : 
                C[i][j] = (C[i - 1][j - 1] + C[i - 1][j]) 
    return C[n][k]

````

### 🟡 AssertionError (WA)

**Example 1**: Task `train_final_00843` (Difficulty: unknown)
- **Prompt**:
> Write a function where a string will start with a specific number.
- **Error**:
````
Traceback (most recent call last):
  File "C:\Users\SHULEO~1\AppData\Local\Temp\tmprd_930xf.py", line 15, in <module>
    test_solve()
  File "C:\Users\SHULEO~1\AppData\Local\Temp\tmprd_930xf.py", line 11, in test_solve
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

**Example 2**: Task `train_final_01512` (Difficulty: unknown)
- **Prompt**:
> Write a function to check if a matrix is symmetric.
- **Error**:
````
Traceback (most recent call last):
  File "C:\Users\SHULEO~1\AppData\Local\Temp\tmp0e7azl_6.py", line 8, in <module>
    test_solve()
  File "C:\Users\SHULEO~1\AppData\Local\Temp\tmp0e7azl_6.py", line 5, in test_solve
    assert is_symmetric([[1, 2], [2, 1]]) == True
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError

````
- **Generated Output** (LLM raw response):
````
def is_symmetric(matrix):
    return matrix == list(map(list, zip(*matrix[::-1])))

````

**Example 3**: Task `train_final_00963` (Difficulty: unknown)
- **Prompt**:
> Given an integer array nums, return the index of the first occurrence of the maximum element.
- **Error**:
````
Traceback (most recent call last):
  File "C:\Users\SHULEO~1\AppData\Local\Temp\tmp_xydpw0d.py", line 17, in <module>
    test_solve()
  File "C:\Users\SHULEO~1\AppData\Local\Temp\tmp_xydpw0d.py", line 15, in test_solve
    assert solve([]) == -1
           ^^^^^^^^^^^^^^^
AssertionError

````
- **Generated Output** (LLM raw response):
````
def solve(nums: list[int]) -> int:
    if not nums:
        return 0
    max_val = float('-inf')
    for i in range(len(nums)):
        if nums[i] > max_val:
            max_val = nums[i]
            idx = i
    return idx

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
