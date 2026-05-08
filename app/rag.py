"""Tiny in-memory RAG over FAQs using OpenAI embeddings + cosine similarity."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List, Tuple

import numpy as np
from groq import Groq

DATA_DIR = Path(__file__).parent / "data"
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

_client: Groq | None = None
_faqs: List[dict] = []
_matrix: np.ndarray | None = None  # shape (N, D), L2-normalized


def _get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq()
    return _client


def _embed(texts: List[str]) -> np.ndarray:
    resp = _get_client().embeddings.create(model=EMBEDDING_MODEL, input=texts)
    vecs = np.array([d.embedding for d in resp.data], dtype=np.float32)
    # L2 normalize for cosine via dot product
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vecs / norms


def load_faqs() -> None:
    """Load FAQs from disk and embed once at startup."""
    global _faqs, _matrix
    with open(DATA_DIR / "faqs.json", "r", encoding="utf-8") as f:
        _faqs = json.load(f)
        print(_faqs)
    if not _faqs:
        _matrix = np.zeros((0, 1), dtype=np.float32)
        return
    texts = [f"Q: {item['q']}\nA: {item['a']}" for item in _faqs]
    _matrix = _embed(texts)
    print(f"[rag] embedded {len(_faqs)} FAQ entries")


def search(query: str, top_k: int = 3) -> List[Tuple[float, dict]]:
    """Return top_k (score, faq) pairs for the given query."""
    if _matrix is None or len(_faqs) == 0:
        return []
    q_vec = _embed([query])[0]
    scores = _matrix @ q_vec  # cosine similarity (already normalized)
    idxs = np.argsort(-scores)[:top_k]
    return [(float(scores[i]), _faqs[i]) for i in idxs]


def search_as_text(query: str, top_k: int = 3) -> str:
    """Format top results as a context string for the LLM."""
    hits = search(query, top_k=top_k)
    if not hits:
        return "No FAQ entries found."
    lines = []
    for score, item in hits:
        lines.append(f"- (relevance {score:.2f}) Q: {item['q']}\n  A: {item['a']}")
    return "\n".join(lines)
