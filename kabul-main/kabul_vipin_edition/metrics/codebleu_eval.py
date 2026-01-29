# -*- coding: utf-8 -*-
"""
CodeBLEU Evaluation Module
Calculates metric semantic similarity score, including:
- N-gram Match: Standard BLEU score
- Weighted N-gram: Weighted n-gram (emphasis on keywords)
- Syntax Match (AST): Abstract Syntax Tree structural similarity (native Tree-sitter implementation)
- Semantic Match (DataFlow): Data flow semantic logic similarity (native Tree-sitter implementation)
"""

from typing import List, Dict, Any, Optional
import sacrebleu
import re
from collections import Counter

# Import native implementation (moved to function to avoid circular import)
# try:
#     from .native_codebleu import calculate_native_codebleu
#     HAS_NATIVE = True
# except ImportError:
#     HAS_NATIVE = False

# C# Keywords (for weighted n-gram)
CSHARP_KEYWORDS = {
    'abstract', 'as', 'base', 'bool', 'break', 'byte', 'case', 'catch',
    'char', 'checked', 'class', 'const', 'continue', 'decimal', 'default',
    'delegate', 'do', 'double', 'else', 'enum', 'event', 'explicit',
    'extern', 'false', 'finally', 'fixed', 'float', 'for', 'foreach',
    'goto', 'if', 'implicit', 'in', 'int', 'interface', 'internal',
    'is', 'lock', 'long', 'namespace', 'new', 'null', 'object', 'operator',
    'out', 'override', 'params', 'private', 'protected', 'public', 'readonly',
    'ref', 'return', 'sbyte', 'sealed', 'short', 'sizeof', 'stackalloc',
    'static', 'string', 'struct', 'switch', 'this', 'throw', 'true',
    'try', 'typeof', 'uint', 'ulong', 'unchecked', 'unsafe', 'ushort',
    'using', 'virtual', 'void', 'volatile', 'while', 'var', 'async', 'await',
    # Common Types
    'String', 'Int32', 'Console', 'Math', 'List', 'Dictionary', 'Array',
}


def tokenize_code(code: str) -> List[str]:
    """Tokenize code into a list of tokens"""
    # Simple tokenization using regex
    tokens = re.findall(r'\b\w+\b|[^\s\w]', code)
    return tokens


def calculate_bleu(predictions: List[str], references: List[str]) -> float:
    """
    Calculate standard BLEU score (using sacrebleu)
    """
    refs = [[r] for r in references]
    bleu = sacrebleu.corpus_bleu(predictions, refs)
    return bleu.score


def calculate_ngram_match(predictions: List[str], references: List[str], n: int = 4) -> float:
    """Calculate n-gram match score"""
    total_score = 0
    
    for pred, ref in zip(predictions, references):
        pred_tokens = tokenize_code(pred)
        ref_tokens = tokenize_code(ref)
        
        scores = []
        for i in range(1, n + 1):
            pred_ngrams = Counter(tuple(pred_tokens[j:j+i]) for j in range(len(pred_tokens) - i + 1))
            ref_ngrams = Counter(tuple(ref_tokens[j:j+i]) for j in range(len(ref_tokens) - i + 1))
            
            if sum(pred_ngrams.values()) == 0:
                scores.append(0)
            else:
                matched = sum((pred_ngrams & ref_ngrams).values())
                scores.append(matched / sum(pred_ngrams.values()))
        
        # Geometric mean
        if all(s > 0 for s in scores):
            import math
            total_score += math.exp(sum(math.log(s) for s in scores) / len(scores))
    
    return total_score / len(predictions) if predictions else 0


def calculate_weighted_ngram_match(predictions: List[str], references: List[str]) -> float:
    """Calculate weighted n-gram match score (keywords have higher weight)"""
    total_score = 0
    
    for pred, ref in zip(predictions, references):
        pred_tokens = tokenize_code(pred)
        ref_tokens = tokenize_code(ref)
        
        # Calculate keyword match
        pred_keywords = [t for t in pred_tokens if t.lower() in CSHARP_KEYWORDS or t in CSHARP_KEYWORDS]
        ref_keywords = [t for t in ref_tokens if t.lower() in CSHARP_KEYWORDS or t in CSHARP_KEYWORDS]
        
        if not ref_keywords:
            keyword_score = 1.0
        else:
            matched = sum(1 for k in pred_keywords if k in ref_keywords)
            keyword_score = matched / len(ref_keywords)
        
        # Normal n-gram
        ngram_score = calculate_ngram_match([pred], [ref])
        
        # Weighted combination
        total_score += 0.7 * ngram_score + 0.3 * keyword_score
    
    return total_score / len(predictions) if predictions else 0


def calculate_syntax_match_fallback(predictions: List[str], references: List[str]) -> float:
    """Syntax structure similarity (Fallback RegEx implementation)"""
    total_score = 0
    structure_patterns = [
        r'\{', r'\}', r'\(', r'\)', r'\[', r'\]', r';',
        r'if\s*\(', r'for\s*\(', r'foreach\s*\(', r'while\s*\(',
        r'switch\s*\(', r'try\s*\{', r'catch\s*\(',
        r'class\s+\w+', r'interface\s+\w+', r'public\s+', r'private\s+',
        r'static\s+', r'=>', r'return\s+',
    ]
    
    for pred, ref in zip(predictions, references):
        pred_structures = []
        ref_structures = []
        for pattern in structure_patterns:
            pred_structures.extend(re.findall(pattern, pred, re.IGNORECASE))
            ref_structures.extend(re.findall(pattern, ref, re.IGNORECASE))
        
        if not ref_structures:
            score = 1.0 if not pred_structures else 0.5
        else:
            pred_counter = Counter(pred_structures)
            ref_counter = Counter(ref_structures)
            matched = sum((pred_counter & ref_counter).values())
            score = matched / sum(ref_counter.values())
        total_score += score
    return total_score / len(predictions) if predictions else 0


def calculate_dataflow_match_fallback(predictions: List[str], references: List[str]) -> float:
    """Data flow similarity (Fallback RegEx implementation)"""
    var_def_patterns = [
        r'\b(var|int|string|float|double|bool|long|char|byte|short)\s+(\w+)\s*=',
        r'\b(List|Dictionary|Array|HashSet|Queue|Stack)<[^>]+>\s+(\w+)\s*=',
        r'(\w+)\s+(\w+)\s*=',
    ]
    var_use_pattern = r'\b([a-z_]\w*)\b'
    
    total_score = 0
    for pred, ref in zip(predictions, references):
        pred_vars = set()
        ref_vars = set()
        for pattern in var_def_patterns:
            for match in re.finditer(pattern, pred, re.IGNORECASE):
                if match.lastindex >= 2: pred_vars.add(match.group(2))
            for match in re.finditer(pattern, ref, re.IGNORECASE):
                if match.lastindex >= 2: ref_vars.add(match.group(2))
        
        pred_uses = set(re.findall(var_use_pattern, pred)) - CSHARP_KEYWORDS
        ref_uses = set(re.findall(var_use_pattern, ref)) - CSHARP_KEYWORDS
        
        if not ref_uses and not ref_vars:
            score = 1.0 if not pred_uses and not pred_vars else 0.5
        else:
            def_score = (len(pred_vars & ref_vars) / len(ref_vars)) if ref_vars else 1.0
            use_score = (len(pred_uses & ref_uses) / len(ref_uses)) if ref_uses else 1.0
            score = 0.5 * def_score + 0.5 * use_score
        total_score += score
    return total_score / len(predictions) if predictions else 0


def calculate_codebleu(
    predictions: List[str],
    references: List[str],
    lang: str = "c_sharp",
    weights: tuple = (0.25, 0.25, 0.25, 0.25)
) -> Dict[str, float]:
    """
    Calculate CodeBLEU comprehensive score
    Priority use native Tree-sitter implementation, fallback if unavailable.
    """
    # Try native implementation
    try:
        from .native_codebleu import calculate_native_codebleu
        # If import succeeds, try to calculate.
        # If calculation fails, it will fall back to the regex implementation.
        result = calculate_native_codebleu(predictions, references, lang, weights)
        result["note"] = "Using native Tree-sitter implementation"
        return result
    except ImportError as e:
        # print(f"Native module import failed (ImportError): {e}")
        pass # Silently fall back if native module is not available
    except Exception as e:
        print(f"Native CodeBLEU calculation error: {e}, fallback to backup implementation")
    
    # Backup implementation
    ngram_score = calculate_ngram_match(predictions, references)
    weighted_ngram_score = calculate_weighted_ngram_match(predictions, references)
    syntax_score = calculate_syntax_match_fallback(predictions, references)
    dataflow_score = calculate_dataflow_match_fallback(predictions, references)
    
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
        "note": "Using fallback Regex implementation"
    }


if __name__ == "__main__":
    # Quick Test
    pred = ["public void Test() { Console.WriteLine(2); }"]
    ref = ["public void Test() { Console.WriteLine(1); }"]
    
    print("\n[CodeBLEU Test]")
    res = calculate_codebleu(pred, ref)
    for k, v in res.items():
        print(f"  {k}: {v}")
    
    if "Native" in res.get("note", ""):
        print(">> Successfully used native implementation")
    else:
        print(">> Used backup implementation:", res.get("note"))
        
    # DataFlow Diff Test
    p_df = "public void M() { int a = 1; int b = a; }"
    r_df = "public void M() { int x = 1; int y = x; }"
    
    print("\n[DataFlow Diff Test (Result)]")
    res_df = calculate_codebleu([p_df], [r_df])
    print(f"  DF Score: {res_df.get('dataflow_match')}")
