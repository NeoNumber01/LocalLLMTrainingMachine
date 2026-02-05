# Evaluation Report

*Generated: 2026-01-29 00:51:34*


## ① Overview

| Field | Value |
|-------|-------|
| Model | deepseek-coder-6.7b-instruct |
| Dataset | test_split.jsonl (200 problems) |
| num_samples | 10 |
| temperature | 0.2 |
| seed | 42 |
| Eval Run ID | `eval_run_2026_01_22_175739` |
| Date | 2026-01-22 |

## ② Core Metrics

| Metric | Value |
|--------|-------|
| **Pass@1** | 39.70% |
| Pass@5 | 59.23% |
| Pass@10 | 64.00% |
| Compile Rate | 85.55% |
| Avg Runtime | 59.7ms |
| P50 Runtime | 46.6ms |
| P95 Runtime | 118.3ms |
| Max Runtime | 1618.8ms |

## ③ Error Analysis

| Error Type | Rate |
|------------|------|
| SyntaxError | 14.45% |
| RuntimeError | 19.30% |
| Timeout | 0.00% |
| AssertionError (WA) | 26.55% |
| ImportError | 0.00% |
| MemoryError | 0.00% |

## ④ Code Quality

| Metric | Value |
|--------|-------|
| Interface Compliance | 100.0% |
| Extra I/O Rate | 15.8% |
| Avg Code Length | 266 chars |
| Avg Lines | 8.7 |

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
| unknown | 39.7% | 85.5% |

### Per-Problem Pass Rate Distribution

> Measures variance across problems - high std indicates uneven difficulty handling

| Statistic | Value |
|-----------|-------|
| Min | 0.0% |
| Median | 30.0% |
| Mean | 39.7% |
| Max | 100.0% |
| Std Dev | 39.0% |
| Total Problems | 2000 |

## ⑥ Failure Case Examples (by Error Type)

> Diverse sampling: different tasks selected to show variety of failures

### 🔴 SyntaxError

**Example 1**: Task `train_final_00963` (Difficulty: unknown)
- **Prompt**:
> Given an integer array nums, return the index of the first occurrence of the maximum element.
- **Error**:
````
Line 1: expected ':'
````
- **Generated Output** (LLM raw response):
````
Here is a simple solution in python using built-in functions max() to find the maximum number and index() function to get its index. 

```python
def solve(nums: list[int]) -> int:
    max_val = max(nums)
    return nums.index(max_val)
```
This will work fine for small lists but if you have large lists with millions of elements this approach could be slow because it has to scan the entire list twice (once for finding the max value and once for getting its index). A more efficient way would be to iterate over the list only once while keeping track of the current maximum and its index. Here's how you can do that:

```python
def solve(nums: list[int]) -int:
    max_idx = 0
    for i in range(len(nums)):
        if nums[i] > nums[max_idx]:
            max_idx = i
    return max_idx
```
In this version of the function we initialize `max_idx` to 0 (the index of the first element), then go through each element in the list. If we encounter an element greater than the one at `max_idx`, we update `max_idx` to the index of this new maximum element. At the end of the loop `max_idx` holds the index of the first occurrence of the maximum element. This version runs in O(n) time where n is the length of the input list.

````

**Example 2**: Task `train_final_00735` (Difficulty: unknown)
- **Prompt**:
> Write a function to convert rgb color to hsv color.
- **Error**:
````
Line 1: expected ':'
````
- **Generated Output** (LLM raw response):
````
Here is the python function that converts RGB colors to HSV colors. 

```python
def rgb_to_hsv(r: float, g: float, b: float) -float:
    # Normalize RGB values between 0-1
    r, g, b = r/255.0, g/255.0, b/255.0
    
    maxc = max(r, g, b)
    minc = min(r, g, b)
    v = maxc
    if minc == maxc:
        return 0.0, 0.0, v
    s = (maxc-minc) / maxc
    rc = (maxc-r) / (maxc-minc)
    gc = (maxc-g) / (maxc-minc)
    bc = (maxc-b) / (maxc-minc)
    if r == maxc:
        h = bc-gc
    elif g == maxc:
        h = 2.0+rc-bc
    else:
        h = 4.0+gc-rc
    h = (h/6.0) % 1.0
    return h*360, s*100, v*100
```
This function takes in three parameters `r`, `g`, and `b` which represent the red, green, and blue components of the RGB color respectively. It returns a tuple containing the hue, saturation, and value of the corresponding HSV color. The returned values are scaled to be within the range [0, 360] for hue, [0, 100] for saturation, and [0, 100] for value.

````

**Example 3**: Task `train_final_00696` (Difficulty: unknown)
- **Prompt**:
> Write a function to caluclate the area of a tetrahedron.
- **Error**:
````
Line 3: expected ':'
````
- **Generated Output** (LLM raw response):
````
Sure, you can calculate the area of a regular tetrahedron using the formula: 
Area = sqrt(3) * side^2. Here is how you could implement this in python:

```python
import math

def area_tetrahedron(side: int) -:
    return math.sqrt(3)*s*s
```
This function takes one argument 'side', which represents the length of any one side of the tetrahedron. It returns the surface area by calculating the square of the side length (`s*s`), multiplying it with `sqrt(3)` to get the area. The result will be returned as output.

````

### 🟠 RuntimeError

**Example 1**: Task `train_final_00847` (Difficulty: unknown)
- **Prompt**:
> Write a python function to find the sum of squares of binomial co-efficients.
- **Error**:
````
Traceback (most recent call last):
  File "C:\Users\SHULEO~1\AppData\Local\Temp\tmpv3tnu7ie.py", line 22, in <module>
    test_solve()
  File "C:\Users\SHULEO~1\AppData\Local\Temp\tmpv3tnu7ie.py", line 17, in test_solve
    assert sum_of_square(4) == 70
           ^^^^^^^^^^^^^
NameError: name 'sum_of_square' is not defined

````
- **Generated Output** (LLM raw response):
````
Sure, here is a simple solution using dynamic programming approach for calculating factorials. The time complexity will be O(n^2). 

```python
def factorial(end: int) -> int:
    fact = [0]*(end+1)
    
    # Base case
    fact[0] = 1
  
    # Calculate factorial from 1 to n
    for i in range(1, end+1):
        fact[i] = i * fact[i-1]
        
    return fact[end]

# Testing the function
print(factorial(5))  # Outputs: 120
```
This function calculates the factorial of all numbers up to 'end' (inclusive), stores them in an array 'fact', and returns the required factorial at index 'end'. If you want to calculate the sum of squares of binomial coefficients, you can use the combination formula `C(n, k) = n! / ((n-k)!*k!)` where `n!` is calculated by this function. You would need to call it twice with different parameters for each term in the sum.

````

**Example 2**: Task `train_final_01405` (Difficulty: unknown)
- **Prompt**:
> Write a function to check if a set is a subset of another.
- **Error**:
````
Traceback (most recent call last):
  File "C:\Users\SHULEO~1\AppData\Local\Temp\tmp2w6aze8m.py", line 12, in <module>
    test_solve()
  File "C:\Users\SHULEO~1\AppData\Local\Temp\tmp2w6aze8m.py", line 9, in test_solve
    assert is_subset({1}, {1, 2}) == True
           ^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\SHULEO~1\AppData\Local\Temp\tmp2w6aze8m.py", line 3, in is_subset
    set1 = set(s1.split(','))
               ^^^^^^^^
AttributeError: 'set' object has no attribute 'split'

````
- **Generated Output** (LLM raw response):
````
Here's the python solution for this problem. This function takes two strings as input where each string represents a set of elements separated by commas. It then converts these strings into sets and checks whether one set is a subset of another using the built-in 'issubset()' method in Python. 

```python
def is_subset(s1: str, s2: str) -> bool:
    # Convert the comma-separated string into a set
    set1 = set(s1.split(','))
    set2 = set(s2.split(','))
    
    return set1.issubset(set2)
```
This function will return True if all elements of `s1` exist in `s2` and False otherwise. Note that it does not consider order or duplicates when checking for subsets. If you need to consider order or duplicates, you would have to use different approach.

````

**Example 3**: Task `train_final_00843` (Difficulty: unknown)
- **Prompt**:
> Write a function where a string will start with a specific number.
- **Error**:
````
Traceback (most recent call last):
  File "C:\Users\SHULEO~1\AppData\Local\Temp\tmp8d6i6jub.py", line 11, in <module>
    test_solve()
  File "C:\Users\SHULEO~1\AppData\Local\Temp\tmp8d6i6jub.py", line 6, in test_solve
    assert match_num('5-2345861')==True
           ^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\SHULEO~1\AppData\Local\Temp\tmp8d6i6jub.py", line 2, in match_num
    print(match_num("123hello")) # Returns: True
          ^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\SHULEO~1\AppData\Local\Tem
````
- **Generated Output** (LLM raw response):
````
Sure, here is the implementation of this function in python:

```python
def match_num(string: str) -> bool:
    return string[0].isdigit()
```
This function checks if the first character of the input string is a digit or not using the `isdigit` method which returns True if all characters are digits else False. 

Here's how you can use it:

```python
print(match_num("123hello")) # Returns: True
print(match_num("hello"))   # Returns: False
```

````

### 🟡 AssertionError (WA)

**Example 1**: Task `train_final_00708` (Difficulty: unknown)
- **Prompt**:
> Write a function to find common index elements from three lists.
- **Error**:
````
Traceback (most recent call last):
  File "C:\Users\SHULEO~1\AppData\Local\Temp\tmp26koi8_b.py", line 13, in <module>
    test_solve()
  File "C:\Users\SHULEO~1\AppData\Local\Temp\tmp26koi8_b.py", line 8, in test_solve
    assert extract_index_list([1, 1, 3, 4, 5, 6, 7],[0, 1, 2, 3, 4, 5, 7],[0, 1, 2, 3, 4, 5, 7])==[1, 7]
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError

````
- **Generated Output** (LLM raw response):
````
Here is the solution in python programming language. This function will return list of indexes where all 3 lists have same element at that position.

```python
def extract_index_list(l1, l2, l3):
    if len(l1) != len(l2) or len(l1) != len(l3):
        raise ValueError("All input lists must be of equal length")
    
    return [i for i in range(len(l1)) if l1[i] == l2[i] == l3[i]]
```
This function works by iterating over each item in `l1` (which we assume has the same length as `l2` and `l3`), checking whether it's also present at the corresponding index in `l2` and `l3`, and adding the index to our result list if so. We use the built-in `range()` function to generate indices, and the `==` operator to compare items at those indices. If the lengths of the lists differ, we throw a `ValueError` exception.

````

**Example 2**: Task `train_final_00083` (Difficulty: unknown)
- **Prompt**:
> Write a function to merge three dictionaries into a single expression.
- **Error**:
````
Traceback (most recent call last):
  File "C:\Users\SHULEO~1\AppData\Local\Temp\tmp3b8bcn56.py", line 10, in <module>
    test_solve()
  File "C:\Users\SHULEO~1\AppData\Local\Temp\tmp3b8bcn56.py", line 6, in test_solve
    assert merge_dictionaries_three({ "R": "Red", "B": "Black", "P": "Pink" }, { "G": "Green", "W": "White" },{"L":"lavender","B":"Blue"})=={'W': 'White', 'P': 'Pink', 'B': 'Black', 'R': 'Red', 'G': 'Green', 'L': 'lavender'}
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
````
- **Generated Output** (LLM raw response):
````
Here is the solution for your problem in python programming language. 

```python
def merge_dictionaries_three(dict1: dict, dict2: dict, dict3: dict) -> dict:
    return {**dict1, **dict2, **dict3}
```
This function uses dictionary unpacking feature of python which allows you to combine multiple dictionaries into one. The '**' operator is used for this purpose. It merges all key-value pairs from the input dictionaries into a new dictionary. If there are duplicate keys, values from the last dictionary will overwrite those from previous ones.

````

**Example 3**: Task `train_final_00843` (Difficulty: unknown)
- **Prompt**:
> Write a function where a string will start with a specific number.
- **Error**:
````
Traceback (most recent call last):
  File "C:\Users\SHULEO~1\AppData\Local\Temp\tmpv6kolwmd.py", line 10, in <module>
    test_solve()
  File "C:\Users\SHULEO~1\AppData\Local\Temp\tmpv6kolwmd.py", line 6, in test_solve
    assert match_num('6-2345861')==False
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError

````
- **Generated Output** (LLM raw response):
````
Sure, here is the python function to check if a string starts with a digit or not. 

```python
def match_num(string: str) -> bool:
    return string[0].isdigit()
```
This function uses the `isdigit` method of string which checks whether the string consists of digits only. The function returns True if the first character of the input string is a digit, otherwise it returns False.

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
