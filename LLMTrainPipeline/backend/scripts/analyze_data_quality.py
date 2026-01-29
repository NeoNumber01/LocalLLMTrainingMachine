#!/usr/bin/env python3
"""
Data Quality Analysis Script for LLMTrainPipeline

Analyzes training data and generates quality metrics for academic-grade reports.
Based on kabul-main/analyze_data_quality.py.

Features:
- Token length distribution (Mean, P50, P95, Max)
- Truncation rate calculation
- Empty/Short sample detection
- Train-Valid leakage check (Exact, Normalized, Jaccard similarity)

Usage:
    from analyze_data_quality import DataQualityAnalyzer
    
    analyzer = DataQualityAnalyzer(tokenizer, max_length=512)
    stats = analyzer.analyze(train_dataset, eval_dataset)
"""

import re
import json
import logging
from dataclasses import dataclass, asdict, field
from typing import Optional, Dict, Any, List, Set
from collections import defaultdict

logger = logging.getLogger("DataQualityAnalyzer")


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class TokenLengthStats:
    """Token length statistics for a dataset"""
    mean: float
    median: float  # P50
    p95: float
    max_length: int
    min_length: int
    total_tokens: int


@dataclass
class TruncationStats:
    """Truncation statistics"""
    max_seq_length: int
    truncated_count: int
    truncated_rate: float
    empty_count: int
    short_count: int  # < 10 tokens
    short_rate: float


@dataclass
class LeakageCheckResult:
    """Train-Valid leakage check result"""
    exact_match_count: int
    exact_match_rate: float
    normalized_match_count: int
    normalized_match_rate: float
    high_similarity_count: int  # Jaccard > threshold
    high_similarity_rate: float
    similarity_threshold: float


@dataclass
class DataQualityStats:
    """Complete data quality statistics"""
    # Sample counts
    train_samples: int
    eval_samples: Optional[int] = None
    
    # Token statistics
    train_token_stats: Optional[TokenLengthStats] = None
    eval_token_stats: Optional[TokenLengthStats] = None
    
    # Truncation
    train_truncation: Optional[TruncationStats] = None
    eval_truncation: Optional[TruncationStats] = None
    
    # Leakage (only if eval dataset provided)
    leakage_check: Optional[LeakageCheckResult] = None
    
    # Overall quality score (0-100)
    quality_score: Optional[float] = None


# ============================================================================
# Analyzer Class
# ============================================================================

class DataQualityAnalyzer:
    """Analyzes data quality for training datasets"""
    
    def __init__(self, tokenizer, max_length: int = 512, similarity_threshold: float = 0.8):
        self.tokenizer = tokenizer
        self.max_length = max_length
        self.similarity_threshold = similarity_threshold
    
    def analyze(self, train_dataset, eval_dataset=None) -> DataQualityStats:
        """
        Analyze training and optional evaluation dataset.
        
        Args:
            train_dataset: Training dataset (HF Dataset or list of dicts)
            eval_dataset: Optional evaluation dataset
            
        Returns:
            DataQualityStats with all computed metrics
        """
        logger.info(f"Analyzing data quality for {len(train_dataset)} train samples...")
        
        # Extract text content from dataset
        train_texts = self._extract_texts(train_dataset)
        eval_texts = self._extract_texts(eval_dataset) if eval_dataset else None
        
        # Token length analysis
        train_token_stats, train_truncation = self._analyze_token_lengths(train_texts, "train")
        
        eval_token_stats = None
        eval_truncation = None
        if eval_texts:
            eval_token_stats, eval_truncation = self._analyze_token_lengths(eval_texts, "eval")
        
        # Leakage check
        leakage_check = None
        if eval_texts:
            leakage_check = self._check_leakage(train_texts, eval_texts)
        
        # Calculate quality score
        quality_score = self._calculate_quality_score(
            train_truncation, leakage_check
        )
        
        stats = DataQualityStats(
            train_samples=len(train_texts),
            eval_samples=len(eval_texts) if eval_texts else None,
            train_token_stats=train_token_stats,
            eval_token_stats=eval_token_stats,
            train_truncation=train_truncation,
            eval_truncation=eval_truncation,
            leakage_check=leakage_check,
            quality_score=quality_score,
        )
        
        logger.info(f"Data quality analysis complete. Quality score: {quality_score:.1f}/100")
        return stats
    
    def _extract_texts(self, dataset) -> List[str]:
        """Extract text content from various dataset formats"""
        if dataset is None:
            return []
        
        texts = []
        for sample in dataset:
            text = None
            
            # Handle different dataset formats
            if isinstance(sample, dict):
                if 'messages' in sample:
                    # Messages format (SFTTrainer)
                    messages = sample['messages']
                    # Concatenate all message contents
                    text = " ".join(m.get('content', '') for m in messages if isinstance(m, dict))
                elif 'text' in sample:
                    text = sample['text']
                elif 'instruction' in sample:
                    instruction = sample.get('instruction', '')
                    output = sample.get('output', sample.get('response', ''))
                    text = f"{instruction} {output}"
                elif 'input' in sample and 'output' in sample:
                    text = f"{sample['input']} {sample['output']}"
            elif isinstance(sample, str):
                text = sample
            
            if text:
                texts.append(text.strip())
        
        return texts
    
    def _analyze_token_lengths(self, texts: List[str], name: str = "dataset"):
        """Analyze token length distribution"""
        if not texts:
            return None, None
        
        logger.info(f"Analyzing token lengths for {len(texts)} {name} samples...")
        
        lengths = []
        truncated = 0
        empty = 0
        short = 0  # < 10 tokens
        
        for text in texts:
            if not text:
                empty += 1
                continue
            
            # Tokenize
            tokens = self.tokenizer(text, add_special_tokens=True, truncation=False)
            length = len(tokens['input_ids'])
            lengths.append(length)
            
            if length > self.max_length:
                truncated += 1
            if length < 10:
                short += 1
        
        if not lengths:
            return None, None
        
        # Calculate statistics
        sorted_lengths = sorted(lengths)
        n = len(sorted_lengths)
        total_tokens = sum(lengths)
        
        token_stats = TokenLengthStats(
            mean=round(total_tokens / n, 1),
            median=sorted_lengths[n // 2],
            p95=sorted_lengths[int(n * 0.95)] if n > 1 else sorted_lengths[0],
            max_length=sorted_lengths[-1],
            min_length=sorted_lengths[0],
            total_tokens=total_tokens,
        )
        
        truncation_stats = TruncationStats(
            max_seq_length=self.max_length,
            truncated_count=truncated,
            truncated_rate=round(truncated / n * 100, 2) if n > 0 else 0,
            empty_count=empty,
            short_count=short,
            short_rate=round(short / n * 100, 2) if n > 0 else 0,
        )
        
        logger.info(f"  Mean: {token_stats.mean}, P95: {token_stats.p95}, "
                   f"Truncation rate: {truncation_stats.truncated_rate}%")
        
        return token_stats, truncation_stats
    
    def _check_leakage(self, train_texts: List[str], eval_texts: List[str]) -> LeakageCheckResult:
        """Check for train-eval data leakage"""
        logger.info("Checking for train-eval leakage...")
        
        if not train_texts or not eval_texts:
            return None
        
        # Build train sets
        train_set = set(train_texts)
        train_normalized = set(self._normalize_text(t) for t in train_texts)
        train_tokens_list = [self._tokenize_for_jaccard(t) for t in train_texts]
        
        exact_match = 0
        normalized_match = 0
        high_similarity = 0
        
        for eval_text in eval_texts:
            # Exact match
            if eval_text in train_set:
                exact_match += 1
            
            # Normalized match
            normalized = self._normalize_text(eval_text)
            if normalized in train_normalized:
                normalized_match += 1
            
            # Jaccard similarity (sample first 100 train for efficiency)
            eval_tokens = self._tokenize_for_jaccard(eval_text)
            max_sim = 0
            for train_tokens in train_tokens_list[:100]:
                sim = self._jaccard_similarity(eval_tokens, train_tokens)
                if sim > max_sim:
                    max_sim = sim
            
            if max_sim > self.similarity_threshold:
                high_similarity += 1
        
        n = len(eval_texts)
        result = LeakageCheckResult(
            exact_match_count=exact_match,
            exact_match_rate=round(exact_match / n * 100, 2) if n > 0 else 0,
            normalized_match_count=normalized_match,
            normalized_match_rate=round(normalized_match / n * 100, 2) if n > 0 else 0,
            high_similarity_count=high_similarity,
            high_similarity_rate=round(high_similarity / n * 100, 2) if n > 0 else 0,
            similarity_threshold=self.similarity_threshold,
        )
        
        logger.info(f"  Exact match: {exact_match} ({result.exact_match_rate}%), "
                   f"Normalized: {normalized_match} ({result.normalized_match_rate}%), "
                   f"High similarity: {high_similarity} ({result.high_similarity_rate}%)")
        
        return result
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text by removing whitespace and comments"""
        # Remove single-line comments
        text = re.sub(r'//.*$', '', text, flags=re.MULTILINE)
        text = re.sub(r'#.*$', '', text, flags=re.MULTILINE)
        # Remove multi-line comments
        text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
        # Remove all whitespace
        text = re.sub(r'\s+', '', text)
        return text.lower()
    
    def _tokenize_for_jaccard(self, text: str) -> Set[str]:
        """Tokenize text for Jaccard similarity (word-level)"""
        tokens = re.split(r'[^a-zA-Z0-9_]+', text)
        return set(t.lower() for t in tokens if t)
    
    def _jaccard_similarity(self, set1: Set[str], set2: Set[str]) -> float:
        """Calculate Jaccard similarity between two sets"""
        if not set1 and not set2:
            return 1.0
        if not set1 or not set2:
            return 0.0
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        return intersection / union
    
    def _calculate_quality_score(self, truncation: TruncationStats, 
                                  leakage: LeakageCheckResult) -> float:
        """Calculate overall quality score (0-100)"""
        score = 100.0
        
        if truncation:
            # Penalize high truncation rate
            if truncation.truncated_rate > 10:
                score -= min(20, truncation.truncated_rate)
            # Penalize empty/short samples
            if truncation.short_rate > 5:
                score -= min(10, truncation.short_rate)
        
        if leakage:
            # Heavy penalty for leakage
            if leakage.exact_match_rate > 0:
                score -= min(30, leakage.exact_match_rate * 10)
            if leakage.high_similarity_rate > 5:
                score -= min(20, leakage.high_similarity_rate * 2)
        
        return max(0, round(score, 1))
    
    def to_dict(self, stats: DataQualityStats) -> Dict[str, Any]:
        """Convert stats to dictionary for JSON serialization"""
        return asdict(stats)
    
    def to_json(self, stats: DataQualityStats) -> str:
        """Convert stats to JSON string"""
        return json.dumps(self.to_dict(stats), indent=2, ensure_ascii=False)


# ============================================================================
# Convenience Functions
# ============================================================================

def analyze_dataset_quality(train_dataset, eval_dataset=None, tokenizer=None, 
                            max_length: int = 512) -> DataQualityStats:
    """
    Convenience function to analyze dataset quality.
    
    If tokenizer is not provided, will attempt to create a simple whitespace tokenizer.
    """
    if tokenizer is None:
        # Fallback: simple whitespace tokenizer
        class SimpleTokenizer:
            def __call__(self, text, **kwargs):
                tokens = text.split()
                return {'input_ids': tokens}
        tokenizer = SimpleTokenizer()
        logger.warning("No tokenizer provided, using simple whitespace tokenizer")
    
    analyzer = DataQualityAnalyzer(tokenizer, max_length)
    return analyzer.analyze(train_dataset, eval_dataset)


def output_data_quality_event(stats: DataQualityStats):
    """Output data quality stats as JSON event for backend parsing"""
    print(json.dumps({
        "type": "data_quality",
        "data": asdict(stats)
    }), flush=True)


if __name__ == "__main__":
    # Test with dummy data
    logging.basicConfig(level=logging.INFO)
    
    class DummyTokenizer:
        def __call__(self, text, **kwargs):
            return {'input_ids': text.split()}
    
    train_data = [
        {"messages": [{"role": "user", "content": "Hello"}, {"role": "assistant", "content": "Hi there!"}]},
        {"messages": [{"role": "user", "content": "Test"}, {"role": "assistant", "content": "Testing 123"}]},
    ]
    
    analyzer = DataQualityAnalyzer(DummyTokenizer(), max_length=10)
    stats = analyzer.analyze(train_data)
    
    print("\n--- Data Quality Stats ---")
    print(analyzer.to_json(stats))
