"""
evaluator.py — Yap Engine V2
Computes a precision-style relevance score for retrieved chunks.
If score < threshold, LangGraph triggers a query rewrite loop.
"""

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity


def score_chunks(query_embedding: list[float], chunk_embeddings: list[list[float]]) -> list[float]:
    """
    Computes cosine similarity between the query and each retrieved chunk.
    Returns a list of float scores in [0, 1].
    """
    if not chunk_embeddings:
        return []

    q = np.array(query_embedding).reshape(1, -1)
    c = np.array(chunk_embeddings)
    scores = cosine_similarity(q, c)[0].tolist()
    return scores


def compute_precision_at_k(scores: list[float], threshold: float = 0.75, k: int = 5) -> dict:
    """
    Computes Precision@K — the fraction of top-K chunks above the relevance threshold.

    This mirrors how Amazon Applied Scientists evaluate retrieval systems:
    - Precision = TP / (TP + FP)
    - Here: relevant chunk = score >= threshold

    Returns:
        dict with precision_at_k, mean_score, passed (bool), and per-chunk scores
    """
    top_k = scores[:k]
    relevant = [s for s in top_k if s >= threshold]
    precision = len(relevant) / len(top_k) if top_k else 0.0
    mean_score = float(np.mean(top_k)) if top_k else 0.0

    return {
        "precision_at_k": round(precision, 4),
        "mean_score": round(mean_score, 4),
        "passed": precision >= 0.5,   # at least half of top-K must be relevant
        "scores": [round(s, 4) for s in top_k],
        "threshold": threshold,
        "k": k,
    }


def rewrite_query(original_query: str) -> str:
    """
    Simple rule-based query rewriter as fallback before calling LLM for rewrite.
    Strips filler words and reformulates as a more precise search query.
    In a production setting, this would call an LLM with a rewrite prompt.
    """
    fillers = ["can you", "please", "tell me", "what is", "explain", "i want to know", "how does"]
    q = original_query.lower().strip()
    for filler in fillers:
        q = q.replace(filler, "").strip()
    # Capitalize and add a trailing question mark if missing
    q = q.capitalize()
    if not q.endswith("?"):
        q += "?"
    return q