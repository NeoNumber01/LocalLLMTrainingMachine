#!/usr/bin/env python3
"""Test post-processing pipeline"""

from postprocess import CodePipeline, PipelineConfig

# Test case 1: Code with Markdown
raw_output_1 = """Here is my solution:

```python
def solve(nums):
    from collections import deque
    q = deque()
    for i in nums:
        q.append(i)
    return len(q)
```

That's my answer!
"""

# Test case 2: Pure code
raw_output_2 = """def solve(nums):
    n = len(nums)
    if n == 0:
        return 0
    return sum(nums) // n
"""

# Test case 3: Code missing import
raw_output_3 = """```python
def solve(nums):
    q = deque()
    for x in nums:
        q.append(x)
    return len(q)
```"""


def test_pipeline():
    pipeline = CodePipeline()
    
    print("=" * 60)
    print("Test 1: Code with Markdown comments")
    print("=" * 60)
    result = pipeline.process(raw_output_1, '', 'def solve(nums: list[int]) -> int:')
    print(f"Success: {result.success}")
    print(f"Phases: {result.phases_completed}")
    print(f"Fixes: {result.fixes_applied}")
    print(f"Logs: {result.logs[-3:] if result.logs else []}")
    print("--- Final code ---")
    print(result.final_code)
    
    print("\n" + "=" * 60)
    print("Test 2: Pure code")
    print("=" * 60)
    result = pipeline.process(raw_output_2, '', 'def solve(nums: list[int]) -> int:')
    print(f"Success: {result.success}")
    print(f"Phases: {result.phases_completed}")
    print("--- Final code ---")
    print(result.final_code)
    
    print("\n" + "=" * 60)
    print("Test 3: Code missing import")
    print("=" * 60)
    result = pipeline.process(raw_output_3, '', 'def solve(nums: list[int]) -> int:')
    print(f"Success: {result.success}")
    print(f"Phases: {result.phases_completed}")
    print(f"Fixes: {result.fixes_applied}")
    print("--- Final code ---")
    print(result.final_code)


if __name__ == "__main__":
    test_pipeline()
