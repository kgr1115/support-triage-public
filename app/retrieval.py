"""Embedding + FAISS retrieval over the KB.

Uses sentence-transformers locally (no API keys) so the retrieval eval works
offline. Index is rebuilt in-process per call to ``build_index`` — for the
fixture-set sizes we evaluate against, build is sub-second after the model
is warm.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer


class _IndexableItem(Protocol):
    """An item the retrieval layer can index — either a KBArticle or a Macro."""

    id: str
    title: str
    body: str

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIM = 384


@lru_cache(maxsize=1)
def _get_model(model_name: str = EMBEDDING_MODEL) -> SentenceTransformer:
    """Cache the embedding model across calls. First call downloads ~80MB on a cold cache."""
    return SentenceTransformer(model_name)


def embed(texts: list[str], *, model_name: str = EMBEDDING_MODEL) -> np.ndarray:
    """Embed a list of texts. Vectors are L2-normalized so inner product == cosine sim."""
    model = _get_model(model_name)
    vectors = model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
    return vectors.astype(np.float32)


@dataclass
class RetrievalIndex:
    """A FAISS index plus the item IDs it was built from."""

    index: faiss.Index
    ids: list[str]

    def search(self, query: str, k: int = 5) -> list[tuple[str, float]]:
        """Return the top-k (id, score) pairs for ``query``, score in [-1, 1]."""
        q = embed([query])
        scores, idxs = self.index.search(q, k)
        results: list[tuple[str, float]] = []
        for rank, i in enumerate(idxs[0].tolist()):
            if i < 0:
                continue
            results.append((self.ids[i], float(scores[0][rank])))
        return results


def build_index(items: list[_IndexableItem]) -> RetrievalIndex:
    """Embed each item (title + body) and build a flat-IP FAISS index.

    Works for KBArticle, Macro, or any object with ``id`` / ``title`` / ``body``.
    """
    if not items:
        raise ValueError("Cannot build an index from zero items.")
    texts = [f"{i.title}\n\n{i.body}" for i in items]
    vectors = embed(texts)
    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(vectors)
    return RetrievalIndex(index=index, ids=[i.id for i in items])
