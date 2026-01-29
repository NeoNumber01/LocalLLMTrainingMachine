# -*- coding: utf-8 -*-
"""
Native CodeBLEU Implementation
Combines Syntax Match and DataFlow Match with standard BLEU.
"""

from typing import List, Dict
from ..codebleu_eval import calculate_ngram_match, calculate_weighted_ngram_match
from .syntax_match import calculate_syntax_match
from .dataflow_match import calculate_dataflow_match

def calculate_native_codebleu(
    predictions: List[str],
    references: List[str],
    lang: str = "c_sharp",
    weights: tuple = (0.25, 0.25, 0.25, 0.25)
) -> Dict[str, float]:
    
    # 1. N-gram Match (Reuse regex implementation as it is standard)
    ngram_score = calculate_ngram_match(predictions, references)
    
    # 2. Weighted N-gram Match
    weighted_ngram_score = calculate_weighted_ngram_match(predictions, references)
    
    # 3. Syntax Match (Native Tree-sitter)
    syntax_score = calculate_syntax_match(predictions, references, lang)
    
    # 4. DataFlow Match (Native Tree-sitter)
    dataflow_score = calculate_dataflow_match(predictions, references, lang)
    
    codebleu_score = (
        weights[0] * ngram_score +
        weights[1] * weighted_ngram_score +
        weights[2] * syntax_score +
        weights[3] * dataflow_score
    )
    
    return {
        "codebleu": codebleu_score,
        "ngram_match": ngram_score,
        "weighted_ngram": weighted_ngram_score,
        "syntax_match": syntax_score,
        "dataflow_match": dataflow_score,
        "note": "Native Tree-sitter Implementation"
    }
