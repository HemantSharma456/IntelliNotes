"""
Tests for retrieval service with deterministic fake embeddings.
"""

import pytest
import numpy as np
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.services.store import StoreService
from app.services.embeddings import EmbeddingService
from app.services.retrieval import RetrievalService


class FakeEmbeddingService:
    """Deterministic embedding service for testing."""

    def __init__(self, tmp_path: Path):
        self._dimension = 4
        self._vectors = []
        self._chunk_ids = []

    def embed_query(self, query: str) -> np.ndarray:
        """Generate a deterministic embedding based on the query string."""
        rng = np.random.RandomState(abs(hash(query)) % (2**31))
        vec = rng.randn(self._dimension).astype(np.float32)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        return vec

    def embed_texts(self, texts: list[str]) -> np.ndarray:
        """Generate deterministic embeddings for texts."""
        vecs = []
        for t in texts:
            rng = np.random.RandomState(abs(hash(t)) % (2**31))
            vec = rng.randn(self._dimension).astype(np.float32)
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec /= norm
            vecs.append(vec)
        return np.array(vecs, dtype=np.float32)

    def add_chunks(self, chunk_ids: list[str], texts: list[str]):
        """Store chunks."""
        self._chunk_ids.extend(chunk_ids)
        if texts:
            embeddings = self.embed_texts(texts)
            self._vectors.extend(embeddings)

    def search(self, query_embedding: np.ndarray, top_k: int = 5,
               allowed_chunk_ids=None) -> list[tuple[str, float]]:
        """Search using simple dot product."""
        if not self._vectors:
            return []

        scores = []
        for i, vec in enumerate(self._vectors):
            chunk_id = self._chunk_ids[i]
            if allowed_chunk_ids is not None and chunk_id not in allowed_chunk_ids:
                continue
            score = float(np.dot(query_embedding, vec))
            scores.append((chunk_id, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    @property
    def total_vectors(self):
        return len(self._vectors)


@pytest.fixture
def test_env(tmp_path):
    """Set up store and fake embedding service."""
    store = StoreService(tmp_path / "test.db")
    emb = FakeEmbeddingService(tmp_path)
    retrieval = RetrievalService(emb, store)

    # Add two documents
    doc1 = store.create_document("database.pdf", "pdf", 1000, num_pages=3)
    doc2 = store.create_document("networks.txt", "txt", 500)

    # Add chunks to doc1
    chunks1 = [
        {"text": "A primary key uniquely identifies each record in a database table.", "page": 1, "start_char": 0, "end_char": 65},
        {"text": "Foreign keys create relationships between tables in relational databases.", "page": 2, "start_char": 65, "end_char": 136},
    ]
    ids1 = store.store_chunks(doc1["id"], chunks1)
    emb.add_chunks(ids1, [c["text"] for c in chunks1])

    # Add chunks to doc2
    chunks2 = [
        {"text": "TCP provides reliable connection-oriented data transmission.", "page": None, "start_char": 0, "end_char": 59},
        {"text": "UDP is a connectionless protocol used for fast data transfer.", "page": None, "start_char": 59, "end_char": 119},
    ]
    ids2 = store.store_chunks(doc2["id"], chunks2)
    emb.add_chunks(ids2, [c["text"] for c in chunks2])

    return {
        "store": store,
        "emb": emb,
        "retrieval": retrieval,
        "doc1": doc1,
        "doc2": doc2,
        "chunk_ids1": ids1,
        "chunk_ids2": ids2,
    }


class TestRetrieval:
    """Tests for the retrieval service."""

    def test_retrieve_all_documents(self, test_env):
        """Retrieve from all documents (no filter)."""
        results = test_env["retrieval"].retrieve("What is a primary key?", top_k=4)
        assert len(results) > 0
        # Should return results from any document
        doc_ids = {r.document_id for r in results}
        assert len(doc_ids) >= 1

    def test_retrieve_filtered_by_document(self, test_env):
        """Retrieve only from a specific document."""
        doc1_id = test_env["doc1"]["id"]
        results = test_env["retrieval"].retrieve(
            "What is a primary key?", top_k=4, document_id=doc1_id
        )
        for r in results:
            assert r.document_id == doc1_id

    def test_retrieve_nonexistent_document(self, test_env):
        """Retrieve from a deleted/missing document returns empty."""
        results = test_env["retrieval"].retrieve(
            "test query", document_id="nonexistent-doc-id"
        )
        assert results == []

    def test_retrieval_results_have_metadata(self, test_env):
        """Each result has required metadata fields."""
        results = test_env["retrieval"].retrieve("database keys", top_k=2)
        for r in results:
            assert r.chunk_id
            assert r.document_id
            assert r.document_name
            assert r.text
            assert isinstance(r.score, float)

    def test_retrieval_ranking(self, test_env):
        """Results are sorted by descending score."""
        results = test_env["retrieval"].retrieve("database", top_k=4)
        if len(results) >= 2:
            scores = [r.score for r in results]
            assert scores == sorted(scores, reverse=True)

    def test_deleted_document_excluded(self, test_env):
        """After deletion, chunks from that document are not retrievable."""
        store = test_env["store"]
        doc1_id = test_env["doc1"]["id"]

        # Delete doc1
        store.delete_document(doc1_id)

        # The retrieval service now should return empty for doc1
        results = test_env["retrieval"].retrieve(
            "primary key", document_id=doc1_id
        )
        assert results == []

    def test_citation_excerpt_correctness(self, test_env):
        """Citation excerpts match actual stored chunk text."""
        results = test_env["retrieval"].retrieve("TCP protocol", top_k=2)
        for r in results:
            chunk = test_env["store"].get_chunk(r.chunk_id)
            assert chunk is not None
            assert r.text == chunk["text"]

    def test_threshold_filtering(self, test_env):
        """Results below threshold are excluded."""
        # With a very high threshold, no results should pass
        results = test_env["retrieval"].retrieve(
            "random query", top_k=4, threshold=0.999
        )
        assert len(results) == 0
