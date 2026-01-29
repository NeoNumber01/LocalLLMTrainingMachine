# -*- coding: utf-8 -*-
"""
Multidimensional Code Translation Evaluation Metrics

Supported Evaluation Dimensions:
1. Semantic Consistency: CodeBLEU, BLEU, Exact Match
2. Executability: Compilation Rate, Syntax Validity
3. Code Quality: Idiom Density, Naming Convention
4. Functional Correctness: Unit Test Pass Rate (MultiPL-E)
"""

from .codebleu_eval import calculate_codebleu, calculate_bleu
from .compilation_eval import check_compilation, calculate_compilation_rate
from .exact_match_eval import calculate_exact_match, normalize_code
from .idiom_eval import calculate_idiom_density, CSHARP_IDIOMS
from .naming_eval import check_naming_conventions
from .syntax_validity_eval import check_syntax_validity, calculate_syntax_validity_rate
from .unit_test_eval import (
    load_multipl_e_dataset,
    run_unit_tests,
    evaluate_unit_test_pass_rate,
)

__all__ = [
    # Semantic Evaluation
    "calculate_codebleu",
    "calculate_bleu",
    "calculate_exact_match",
    "normalize_code",
    # Executability Evaluation
    "check_compilation",
    "calculate_compilation_rate",
    "check_syntax_validity",
    "calculate_syntax_validity_rate",
    # Code Quality Evaluation
    "calculate_idiom_density",
    "CSHARP_IDIOMS",
    "check_naming_conventions",
    # Unit Test Evaluation
    "load_multipl_e_dataset",
    "run_unit_tests",
    "evaluate_unit_test_pass_rate",
]
