# Evaluation Report

*Generated: 2026-01-29 00:56:00*


## ① Overview

| Field | Value |
|-------|-------|
| Model | qwen2.5-coder-3B-Instruct |
| Dataset | test_split.jsonl (200 problems) |
| num_samples | 10 |
| temperature | 0.2 |
| seed | 42 |
| Eval Run ID | `eval_run_2026_01_23_174110` |
| Date | 2026-01-23 |

## ② Core Metrics

| Metric | Value |
|--------|-------|
| **Pass@1** | 61.20% |
| Pass@5 | 67.29% |
| Pass@10 | 69.00% |
| Compile Rate | 98.85% |
| Avg Runtime | 50.3ms |
| P50 Runtime | 45.0ms |
| P95 Runtime | 107.3ms |
| Max Runtime | 206.4ms |

## ③ Error Analysis

| Error Type | Rate |
|------------|------|
| SyntaxError | 1.15% |
| RuntimeError | 10.75% |
| Timeout | 0.05% |
| AssertionError (WA) | 26.85% |
| ImportError | 0.00% |
| MemoryError | 0.00% |

## ④ Code Quality

| Metric | Value |
|--------|-------|
| Interface Compliance | 100.0% |
| Extra I/O Rate | 0.1% |
| Avg Code Length | 137 chars |
| Avg Lines | 5.2 |

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
| unknown | 61.2% | 98.9% |

### Per-Problem Pass Rate Distribution

> Measures variance across problems - high std indicates uneven difficulty handling

| Statistic | Value |
|-----------|-------|
| Min | 0.0% |
| Median | 100.0% |
| Mean | 61.2% |
| Max | 100.0% |
| Std Dev | 46.0% |
| Total Problems | 2000 |

## ⑥ Failure Case Examples (by Error Type)

> Diverse sampling: different tasks selected to show variety of failures

### 🔴 SyntaxError

**Example 1**: Task `train_final_00083` (Difficulty: unknown)
- **Prompt**:
> Write a function to merge three dictionaries into a single expression.
- **Error**:
````
Line 2: invalid syntax
````
- **Generated Output** (LLM raw response):
````
def merge_dictionaries_three(dict1,dict2,dict3):
  merged_dict = {**dict1,**dict2,**dict3}
  return merged_dict
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
def merge_dictionaries_three(dict1,dict2,dict3):
  res = {**dict1, **dict2, **dict3}
  return (res)
````

**Example 3**: Task `train_final_00083` (Difficulty: unknown)
- **Prompt**:
> Write a function to merge three dictionaries into a single expression.
- **Error**:
````
Line 2: invalid syntax
````
- **Generated Output** (LLM raw response):
````
def merge_dictionaries_three(dict1,dict2,dict3):
  merged_dict = {**dict1,**dict2,**dict3}
  return merged_dict
````

### 🟠 RuntimeError

**Example 1**: Task `train_final_00708` (Difficulty: unknown)
- **Prompt**:
> Write a function to find common index elements from three lists.
- **Error**:
````
Traceback (most recent call last):
  File "C:\Users\SHULEO~1\AppData\Local\Temp\tmpwbicor2x.py", line 13, in <module>
    test_solve()
  File "C:\Users\SHULEO~1\AppData\Local\Temp\tmpwbicor2x.py", line 8, in test_solve
    assert extract_index_list([1, 1, 3, 4, 5, 6, 7],[0, 1, 2, 3, 4, 5, 7],[0, 1, 2, 3, 4, 5, 7])==[1, 7]
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\SHULEO~1\AppData\Local\Temp\tmpwbicor2x.py", line 4, in extrac
````
- **Generated Output** (LLM raw response):
````
def extract_index_list(l1,l2,l3):
    result = []
    for i in range(len(l1)):
        if l1[i] == l2[i] == l3[i]:
            result.append(l1[i])
    return result
````

**Example 2**: Task `train_final_00516` (Difficulty: unknown)
- **Prompt**:
> Write a function to flatten the tuple list to a string.
- **Error**:
````
Traceback (most recent call last):
  File "C:\Users\SHULEO~1\AppData\Local\Temp\tmp3s3yl6ek.py", line 11, in <module>
    test_solve()
  File "C:\Users\SHULEO~1\AppData\Local\Temp\tmp3s3yl6ek.py", line 6, in test_solve
    assert flatten_tuple([('1', '4', '6'), ('5', '8'), ('2', '9'), ('1', '10')]) == '1 4 6 5 8 2 9 1 10'
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\SHULEO~1\AppData\Local\Temp\tmp3s3yl6ek.py", line 2, in flatten_tuple
    res 
````
- **Generated Output** (LLM raw response):
````
def flatten_tuple(test_list):
  res = ''.join([ele for ele in test_list])
  return (res)
````

**Example 3**: Task `train_final_00630` (Difficulty: unknown)
- **Prompt**:
> Write a python function to set the right most unset bit.
- **Error**:
````
Traceback (most recent call last):
  File "C:\Users\SHULEO~1\AppData\Local\Temp\tmpssww6pmz.py", line 16, in <module>
    test_solve()
  File "C:\Users\SHULEO~1\AppData\Local\Temp\tmpssww6pmz.py", line 11, in test_solve
    assert set_Right_most_Unset_Bit(21) == 23
           ^^^^^^^^^^^^^^^^^^^^^^^^
NameError: name 'set_Right_most_Unset_Bit' is not defined

````
- **Generated Output** (LLM raw response):
````
def get_Pos_Of_Right_most_Set_Bit(n): 
    if (n == 0): 
        return 0
    pos = 1
    while ((n & 1) == 1): 
        n >>= 1
        pos += 1
    return pos
````

### 🟡 AssertionError (WA)

**Example 1**: Task `train_final_00843` (Difficulty: unknown)
- **Prompt**:
> Write a function where a string will start with a specific number.
- **Error**:
````
Traceback (most recent call last):
  File "C:\Users\SHULEO~1\AppData\Local\Temp\tmp8ex2bcgf.py", line 15, in <module>
    test_solve()
  File "C:\Users\SHULEO~1\AppData\Local\Temp\tmp8ex2bcgf.py", line 10, in test_solve
    assert match_num('5-2345861')==True
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError

````
- **Generated Output** (LLM raw response):
````
import re
def match_num(string):
  text = re.compile(r'^\d')
  if text.match(string):
    return 'Found a match!'
  else:
    return ('Not matched!')
````

**Example 2**: Task `train_final_00668` (Difficulty: unknown)
- **Prompt**:
> Write a function to check if the given tuple contains all valid values or not.
- **Error**:
````
Traceback (most recent call last):
  File "C:\Users\SHULEO~1\AppData\Local\Temp\tmp9bnauwe1.py", line 11, in <module>
    test_solve()
  File "C:\Users\SHULEO~1\AppData\Local\Temp\tmp9bnauwe1.py", line 7, in test_solve
    assert check_valid((True, False, True, True) ) == False
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError

````
- **Generated Output** (LLM raw response):
````
def check_valid(test_tup):
  res = all(isinstance(ele, (int, float)) for ele in test_tup)
  return (res)
````

**Example 3**: Task `train_final_00543` (Difficulty: unknown)
- **Prompt**:
> Write a python function to check whether an array is subarray of another or not.
- **Error**:
````
Traceback (most recent call last):
  File "C:\Users\SHULEO~1\AppData\Local\Temp\tmp6vcyir1x.py", line 24, in <module>
    test_solve()
  File "C:\Users\SHULEO~1\AppData\Local\Temp\tmp6vcyir1x.py", line 19, in test_solve
    assert is_Sub_Array([1,4,3,5],[1,2],4,2) == False
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError

````
- **Generated Output** (LLM raw response):
````
def is_Sub_Array(A,B,n,m): 
	if (n == 0): 
		return True
	if (m == 0): 
		return False
	if (A[n-1] != B[m-1]): 
		return is_Sub_Array(A, B, n - 1, m) 
	else: 
		return is_Sub_Array(A, B, n - 1, m - 1) 
def is_SubArray(A, B, n, m): 
	for i in range(m): 
		for j in range(n): 
			if (B[i] == A[j]): 
				if (is_Sub_Array(A, B, n, m)): 
					return True
	return False
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
