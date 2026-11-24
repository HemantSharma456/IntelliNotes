"""
Embedding service using Sentence Transformers and FAISS.
"""

import json
import logging
import numpy as np
from pathlib import Path
from typing import Optional

import faiss
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Manages embedding generation and FAISS index."""

    def __init__(self, model_name: str, index_path: Path, chunk_map_path: Path):
        self.model_name = model_name
        self.index_path = index_path
        self.chunk_map_path = chunk_map_path
        self._model: Optional[SentenceTransformer] = None
        self._index: Optional[faiss.IndexFlatIP] = None
        # Maps FAISS vector position → chunk_id
        self._chunk_ids: list[str] = []
        self._dimension: int = 384  # all-MiniLM-L6-v2 dimension

        self._load_or_create_index()

    @property
    def model(self) -> SentenceTransformer:
        if self._model is None:
            logger.info(f"Loading embedding model: {self.model_name}")
            self._model = SentenceTransformer(self.model_name)
            self._dimension = self._model.get_sentence_embedding_dimension()
        return self._model

    def _load_or_create_index(self):
        """Load existing FAISS index or create a new one."""
        if self.index_path.exists() and self.chunk_map_path.exists():
            try:
                self._index = faiss.read_index(str(self.index_path))
                with open(self.chunk_map_path, "r") as f:
                    self._chunk_ids = json.load(f)
                logger.info(
                    f"Loaded FAISS index with {self._index.ntotal} vectors, "
                    f"{len(self._chunk_ids)} chunk mappings"
                )
                return
            except Exception as e:
                logger.warning(f"Failed to load FAISS index: {e}. Creating new index.")

        self._index = faiss.IndexFlatIP(self._dimension)
        self._chunk_ids = []

    def _save_index(self):
        """Persist the FAISS index and chunk mapping."""
        faiss.write_index(self._index, str(self.index_path))
        with open(self.chunk_map_path, "w") as f:
            json.dump(self._chunk_ids, f)

    def embed_texts(self, texts: list[str]) -> np.ndarray:
        """Generate normalized embeddings for a list of texts."""
        embeddings = self.model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
        # Normalize for cosine similarity via inner product
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms[norms == 0] = 1  # Avoid division by zero
        embeddings = embeddings / norms
        return embeddings.astype(np.float32)

    def embed_query(self, query: str) -> np.ndarray:
        """Generate a normalized embedding for a single query."""
        return self.embed_texts([query])[0]

    def add_chunks(self, chunk_ids: list[str], texts: list[str]):
        """Embed texts and add them to the FAISS index."""
        if not texts:
            return
        embeddings = self.embed_texts(texts)
        self._index.add(embeddings)
        self._chunk_ids.extend(chunk_ids)
        self._save_index()

    def search(
        self,
        query_embedding: np.ndarray,
        top_k: int = 5,
        allowed_chunk_ids: Optional[set[str]] = None,
    ) -> list[tuple[str, float]]:
        """
        Search the FAISS index for similar chunks.

        Args:
            query_embedding: Normalized query vector.
            top_k: Number of results to return.
            allowed_chunk_ids: If provided, only return results from these chunk IDs.

        Returns:
            List of (chunk_id, score) tuples, sorted by descending score.
        """
        if self._index.ntotal == 0:
            return []

        # When filtering by allowed chunk IDs (e.g. a specific video or document),
        # search through all available vectors in the index so chunks are not prematurely omitted
        if allowed_chunk_ids is not None:
            search_k = self._index.ntotal
        else:
            search_k = min(self._index.ntotal, top_k)

        query_vec = query_embedding.reshape(1, -1).astype(np.float32)
        scores, indices = self._index.search(query_vec, search_k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self._chunk_ids):
                continue
            chunk_id = self._chunk_ids[idx]
            if allowed_chunk_ids is not None and chunk_id not in allowed_chunk_ids:
                continue
            results.append((chunk_id, float(score)))
            if len(results) >= top_k:
                break

        return results

    def rebuild_index(self, chunk_ids: list[str], texts: list[str]):
        """Rebuild the FAISS index from scratch with the given chunks."""
        self._index = faiss.IndexFlatIP(self._dimension)
        self._chunk_ids = []

        if texts:
            embeddings = self.embed_texts(texts)
            self._index.add(embeddings)
            self._chunk_ids = list(chunk_ids)

        self._save_index()
        logger.info(f"Rebuilt FAISS index with {len(texts)} vectors")

    def remove_chunks(
        self,
        chunk_ids_to_remove: set[str],
        remaining_chunks: Optional[tuple[list[str], list[str]]] = None,
    ):
        """Remove specific chunk IDs from FAISS index and persist."""
        if remaining_chunks is not None:
            ids, texts = remaining_chunks
            self.rebuild_index(ids, texts)
        else:
            keep_indices = [
                i for i, cid in enumerate(self._chunk_ids) if cid not in chunk_ids_to_remove
            ]
            if len(keep_indices) == len(self._chunk_ids):
                return
            if keep_indices and self._index.ntotal > 0:
                remaining_vecs = np.array(
                    [self._index.reconstruct(i) for i in keep_indices], dtype=np.float32
                )
                self._index = faiss.IndexFlatIP(self._dimension)
                self._index.add(remaining_vecs)
                self._chunk_ids = [self._chunk_ids[i] for i in keep_indices]
            else:
                self._index = faiss.IndexFlatIP(self._dimension)
                self._chunk_ids = []
            self._save_index()

    @property
    def total_vectors(self) -> int:
        return self._index.ntotal if self._index else 0
