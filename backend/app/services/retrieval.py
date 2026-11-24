"""
Retrieval service: semantic search with document filtering.
"""

import logging
from typing import Optional

from app.services.embeddings import EmbeddingService
from app.services.store import StoreService

logger = logging.getLogger(__name__)


class RetrievalResult:
    """A single retrieval result with chunk data and score (supports both documents and videos)."""

    def __init__(
        self,
        chunk_id: str,
        document_id: Optional[str] = None,
        document_name: Optional[str] = None,
        text: str = "",
        page: Optional[int] = None,
        score: float = 0.0,
        source_type: str = "document",
        video_id: Optional[str] = None,
        video_title: Optional[str] = None,
        channel: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        timestamp_url: Optional[str] = None,
    ):
        self.chunk_id = chunk_id
        self.document_id = document_id or ""
        self.document_name = document_name or ""
        self.text = text
        self.page = page
        self.score = score
        self.source_type = source_type
        self.video_id = video_id
        self.video_title = video_title
        self.channel = channel
        self.start_time = start_time
        self.end_time = end_time
        self.timestamp_url = timestamp_url

    def to_dict(self) -> dict:
        d = {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "document_name": self.document_name,
            "text": self.text,
            "page": self.page,
            "score": self.score,
            "source_type": self.source_type,
        }
        if self.source_type == "video":
            d.update({
                "video_id": self.video_id,
                "video_title": self.video_title,
                "channel": self.channel,
                "start_time": self.start_time,
                "end_time": self.end_time,
                "timestamp_url": self.timestamp_url,
            })
        return d


class RetrievalService:
    """Performs semantic search over stored document and video chunks."""

    def __init__(self, embedding_service: EmbeddingService, store: StoreService):
        self.embedding_service = embedding_service
        self.store = store

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        document_id: Optional[str] = None,
        video_id: Optional[str] = None,
        source_type: Optional[str] = "document",
        threshold: float = 0.0,
    ) -> list[RetrievalResult]:
        """
        Retrieve relevant chunks for a query across documents, videos, or both.

        Args:
            query: The user's question or search query.
            top_k: Maximum number of chunks to retrieve.
            document_id: If provided, only search within this document.
            video_id: If provided, only search within this video.
            source_type: 'document' (default), 'video', or 'all'.
            threshold: Minimum similarity score threshold.

        Returns:
            List of RetrievalResult sorted by descending score.
        """
        # Generate query embedding
        query_embedding = self.embedding_service.embed_query(query)

        # Determine allowed chunk IDs for filtering
        allowed_chunk_ids = None

        if document_id:
            doc = self.store.get_document(document_id)
            if doc is None:
                return []
            chunks = self.store.get_chunks_by_document(document_id)
            allowed_chunk_ids = {c["id"] for c in chunks}
            if not allowed_chunk_ids:
                return []
        elif video_id:
            vid = self.store.get_video(video_id)
            if vid is None:
                return []
            chunks = self.store.get_video_chunks(video_id)
            allowed_chunk_ids = {c["id"] for c in chunks}
            if not allowed_chunk_ids:
                return []
        elif source_type in ("document", "documents"):
            doc_chunk_ids = self.store.get_all_chunk_ids()
            allowed_chunk_ids = set(doc_chunk_ids)
            if not allowed_chunk_ids:
                return []
        elif source_type in ("video", "videos"):
            vid_chunk_ids = self.store.get_all_video_chunk_ids()
            allowed_chunk_ids = set(vid_chunk_ids)
            if not allowed_chunk_ids:
                return []

        # Search FAISS index
        raw_results = self.embedding_service.search(
            query_embedding, top_k=top_k, allowed_chunk_ids=allowed_chunk_ids
        )

        if not raw_results:
            return []

        # Adapt threshold for spoken/conversational video transcripts
        effective_threshold = threshold
        if video_id:
            # When scoping to a specific video, accept lower conversational similarity or fallback to top chunks
            effective_threshold = min(threshold, 0.05) if threshold > 0 else 0.0
        elif source_type in ("video", "videos"):
            effective_threshold = min(threshold, 0.08) if threshold > 0 else 0.0

        # Build results with metadata using unified chunk lookup
        chunk_ids_to_fetch = [cid for cid, score in raw_results if score >= effective_threshold]
        if not chunk_ids_to_fetch and (video_id or source_type in ("video", "videos")) and raw_results:
            # Fall back to top available video chunks
            chunk_ids_to_fetch = [cid for cid, _ in raw_results[:top_k]]

        if not chunk_ids_to_fetch:
            return []

        score_map = dict(raw_results)
        chunks_meta = self.store.get_chunks_by_ids_any(chunk_ids_to_fetch)
        meta_by_id = {c["id"]: c for c in chunks_meta}

        results = []
        for chunk_id in chunk_ids_to_fetch:
            chunk = meta_by_id.get(chunk_id)
            if not chunk:
                continue

            score = score_map.get(chunk_id, 0.0)
            if chunk.get("source_type") == "video":
                results.append(
                    RetrievalResult(
                        chunk_id=chunk_id,
                        text=chunk["text"],
                        score=score,
                        source_type="video",
                        video_id=chunk.get("video_id"),
                        video_title=chunk.get("source_name"),
                        channel=chunk.get("channel"),
                        start_time=chunk.get("start_time"),
                        end_time=chunk.get("end_time"),
                        timestamp_url=chunk.get("timestamp_url"),
                    )
                )
            else:
                results.append(
                    RetrievalResult(
                        chunk_id=chunk_id,
                        document_id=chunk.get("document_id"),
                        document_name=chunk.get("source_name"),
                        text=chunk["text"],
                        page=chunk.get("page"),
                        score=score,
                        source_type="document",
                    )
                )

        return results

    def retrieve_video(
        self,
        query: str,
        top_k: int = 5,
        video_id: Optional[str] = None,
        threshold: float = 0.25,
    ) -> list[RetrievalResult]:
        """Convenience method for video-specific semantic retrieval."""
        return self.retrieve(
            query=query,
            top_k=top_k,
            video_id=video_id,
            source_type="video",
            threshold=threshold,
        )

    async def retrieve_async(
        self,
        query: str,
        top_k: int = 5,
        document_id: Optional[str] = None,
        video_id: Optional[str] = None,
        source_type: Optional[str] = "document",
        threshold: float = 0.0,
    ) -> list[RetrievalResult]:
        """
        Asynchronously retrieve relevant chunks without blocking the event loop.
        """
        import asyncio
        return await asyncio.to_thread(
            self.retrieve,
            query=query,
            top_k=top_k,
            document_id=document_id,
            video_id=video_id,
            source_type=source_type,
            threshold=threshold,
        )

    async def retrieve_video_async(
        self,
        query: str,
        top_k: int = 5,
        video_id: Optional[str] = None,
        threshold: float = 0.25,
    ) -> list[RetrievalResult]:
        """Asynchronously retrieve relevant video segments."""
        import asyncio
        return await asyncio.to_thread(
            self.retrieve_video,
            query=query,
            top_k=top_k,
            video_id=video_id,
            threshold=threshold,
        )

