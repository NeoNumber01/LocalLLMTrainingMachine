# Dataset Detailed Analysis Report

**Generated**: January 25, 2026

---

## 1. Basic Statistics

| Dataset | Sample Count | File Size |
|---------|--------------|-----------|
| train_split | 1600 | ~977 KB |
| valid_split | 200 | ~107 KB |
| test_split | 200 | ~104 KB |
| **Total** | **2000** | **~1.19 MB** |

## 2. Data Split Ratio

- **Training Set (Train)**: 1600 samples (80.0%)
- **Validation Set (Valid)**: 200 samples (10.0%)
- **Test Set (Test)**: 200 samples (10.0%)

## 3. Data Field Structure

Each data sample contains the following fields:

| Field Name | Type | Description | Required |
|------------|------|-------------|----------|
| `id` | string | Unique identifier | ✅ |
| `instruction` | string | Programming task description | ✅ |
| `signature` | string | Function signature | ✅ |
| `reference` | string | Reference solution code | ✅ |
| `tests` | string | Test cases | ✅ |
| `_category` | string | Problem category | ❌ (optional) |
| `_difficulty` | int | Difficulty level (1-10) | ❌ (optional) |

## 4. Text Length Statistics

### 4.1 Instruction (Task Description) Length

- Minimum: 22 characters
- Maximum: 249 characters
- Average: 72.89 characters

### 4.2 Reference (Reference Code) Length

- Minimum: 29 characters
- Maximum: 1331 characters
- Average: 206.13 characters

### 4.3 Signature (Function Signature) Length

- Minimum: 12 characters
- Maximum: 92 characters
- Average: 41.41 characters

## 5. Problem Category Distribution

| Category | Count | Percentage |
|----------|-------|------------|
| Uncategorized | 1886 | 94.3% |
| list/array | 73 | 3.6% |
| string | 17 | 0.9% |
| math | 15 | 0.8% |
| other | 2 | 0.1% |
| set | 2 | 0.1% |
| dp | 1 | 0.1% |
| matrix | 1 | 0.1% |
| extraction | 1 | 0.1% |
| conversion | 1 | 0.1% |
| validation | 1 | 0.1% |

## 6. Difficulty Level Distribution

| Difficulty Level | Count | Percentage |
|------------------|-------|------------|
| 10 | 22 | 1.1% |
| 7 | 42 | 2.1% |
| 8 | 32 | 1.6% |
| 9 | 18 | 0.9% |
| Unlabeled | 1886 | 94.3% |

## 7. Test Case Statistics

- Total test cases: 4892
- Average test cases per problem: 2.45
- Minimum test cases: 0
- Maximum test cases: 5

## 8. Reference Code Library Usage Statistics

| Library | Usage Count |
|---------|-------------|
| `math` | 91 |
| `collections` | 80 |
| `re` | 79 |
| `heapq` | 39 |
| `itertools` | 18 |
| `sys` | 8 |
| `bisect` | 8 |
| `statistics` | 5 |
| `cmath` | 4 |
| `random` | 4 |
| `operator` | 3 |
| `array` | 3 |
| `os` | 3 |
| `json` | 2 |
| `functools` | 2 |
| `datetime` | 2 |
| `copy` | 1 |

## 9. Data Sample Examples

### Example 1 (Simple)

```json
{
  "id": "train_final_00016",
  "instruction": "Write a function to find the perimeter of a square.",
  "signature": "def square_perimeter(a: Any) -> int:",
  "reference": "def square_perimeter(a):\r\n  perimeter=4*a\r\n  return perimeter",
  "tests": "def test_solve():\n    assert square_perimeter(10)==40\n    assert square_perimeter(5)==20\n    assert square_perimeter(4)==16\n"
}
```

### Example 2 (With Category)

```json
{
  "id": "train_final_00001",
  "instruction": "Write a function to find the minimum cost path to reach (m, n) from (0, 0) for the given cost matrix cost[][] and a position (m, n) in cost[][].",
  "signature": "def min_cost(cost: Any, m: int, n: int) -> int:",
  "reference": "R = 3\r\nC = 3\r\ndef min_cost(cost, m, n): \r\n\ttc = [[0 for x in range(C)] for x in range(R)] \r\n\ttc[0][0] = cost[0][0] \r\n\tfor i in range(1, m+1): \r\n\t\ttc[i][0] = tc[i-1][0] + cost[i][0] \r\n\tfor j in range(1, n+1): \r\n\t\ttc[0][j] = tc[0][j-1] + cost[0][j] \r\n\tfor i in range(1, m+1): \r\n\t\tfor j in range(1, n+1): \r\n\t\t\ttc[i][j] = min(tc[i-1][j-1], tc[i-1][j], tc[i][j-1]) + cost[i][j] \r\n\treturn tc[m][n]",
  "tests": "def test_solve():\n    assert min_cost([[1, 2, 3], [4, 8, 2], [1, 5, 3]], 2, 2) == 8\n    assert min_cost([[2, 3, 4], [5, 9, 3], [2, 6, 4]], 2, 2) == 12\n    assert min_cost([[3, 4, 5], [6, 10, 4], [3, 7, 5]], 2, 2) == 16\n",
  "_category": "dp",
  "_difficulty": 8
}
```

## 10. Data Quality Assessment

### 10.1 Required Field Completeness

✅ All required fields are complete, no missing values

### 10.2 Data Format Consistency

✅ All data uses unified JSONL format
✅ Field naming conventions are consistent
✅ ID format is unified (train_final_XXXXX)

## 11. Summary

### Dataset Characteristics

1. **Task Type**: Python programming code generation tasks
2. **Data Scale**: 2003 high-quality programming problems in total
3. **Data Split**: Training/Validation/Test set ratio is approximately 80%/10%/10%
4. **Annotation Completeness**: All required fields are complete, some problems have category and difficulty annotations
5. **Test Coverage**: Each problem has an average of 3 test cases

### Applicable Scenarios

- Code Generation Fine-tuning
- Instruction Following Training
- Programming Benchmark Evaluation
