"""
API routes for IntelliNotes backend.
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, UploadFile, HTTPException, Depends
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse


from app.models.schemas import (
    ChatRequest,
    ChatResponse,
    Citation,
    DocumentDeleteResponse,
    DocumentListResponse,
    DocumentMeta,
    FlashcardResponse,
    HealthResponse,
    MCQResponse,
    StudyToolRequest,
    SummaryResponse,
    VideoChunkMeta,
    VideoDeleteResponse,
    VideoDetailResponse,
    VideoIngestRequest,
    VideoIngestResponse,
    VideoListResponse,
    VideoMeta,
    VideoSearchRequest,
    VideoSearchResponse,
    VideoSearchResult,
    VideoSuggestion,
    VideoSuggestionsResponse,
    VideoRecommendationResponse,
    WorkspaceVideoMatch,
    VivaResponse,
    VideoSummaryRequest,
    VideoSummaryResponse,
)
from app.services.documents import ExtractionError, ScannedPDFError, extract_text
from app.services.chunking import chunk_text
from app.services.llm import LLMServiceError
from app.services.video import TranscriptUnavailableError, VideoService

logger = logging.getLogger(__name__)

router = APIRouter()

# These will be injected by main.py
_app_state = {}

ALLOWED_EXTENSIONS = {"pdf", "txt"}


def get_state():
    """Get shared application state (services)."""
    return _app_state


def set_state(state: dict):
    """Set shared application state."""
    global _app_state
    _app_state = state


# ── Health ────────────────────────────────────────────────────────────────────

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Check service health and configuration status."""
    state = get_state()
    settings = state["settings"]
    store = state["store"]
    return HealthResponse(
        status="ok",
        gemini_configured=bool(settings.GEMINI_API_KEY),
        embedding_model=settings.EMBEDDING_MODEL,
        documents_count=store.count_documents(),
    )


# ── Documents ─────────────────────────────────────────────────────────────────

@router.post("/documents/upload", response_model=DocumentMeta, status_code=201)
async def upload_document(file: UploadFile = File(...)):
    """Upload and process a PDF or TXT file."""
    state = get_state()
    settings = state["settings"]
    store = state["store"]
    embedding_service = state["embedding_service"]

    # Validate file extension
    if not file.filename:
        raise HTTPException(status_code=422, detail="No filename provided")

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type: .{ext}. Supported: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # Read file content
    content = await file.read()

    # Validate file size
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {settings.MAX_UPLOAD_MB}MB.",
        )

    if len(content) == 0:
        raise HTTPException(status_code=422, detail="Uploaded file is empty")

    # Save to uploads directory
    upload_path = settings.uploads_path / f"{os.urandom(8).hex()}_{file.filename}"
    upload_path.write_bytes(content)

    try:
        # Extract text
        text, page_breaks, num_pages = extract_text(upload_path, ext)

        # Chunk the text
        chunks = chunk_text(
            text,
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
            page_breaks=page_breaks,
        )

        if not chunks:
            raise ExtractionError("No readable text chunks could be extracted from this document.")

        # Create document record
        doc = store.create_document(
            filename=file.filename,
            file_type=ext,
            file_size=len(content),
            num_pages=num_pages,
            file_path=str(upload_path),
        )

        # Store chunks
        chunk_ids = store.store_chunks(doc["id"], chunks)

        # Generate embeddings and add to FAISS index
        chunk_texts = [c["text"] for c in chunks]
        embedding_service.add_chunks(chunk_ids, chunk_texts)

        # Update chunk count
        doc["num_chunks"] = len(chunks)

        return DocumentMeta(**doc)

    except ScannedPDFError as e:
        upload_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=str(e))
    except ExtractionError as e:
        upload_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        upload_path.unlink(missing_ok=True)
        logger.exception("Upload processing failed")
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


@router.get("/documents", response_model=DocumentListResponse)
async def list_documents():
    """List all uploaded documents."""
    state = get_state()
    store = state["store"]
    docs = store.get_all_documents()
    return DocumentListResponse(
        documents=[DocumentMeta(**d) for d in docs]
    )


@router.get("/documents/{document_id}/file")
async def get_document_file(document_id: str):
    """
    Stream the uploaded document file (PDF or TXT) inline for in-app showcase preview.
    """
    state = get_state()
    store = state["store"]
    settings = state["settings"]

    doc = store.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    file_path: Optional[Path] = None
    if doc.get("file_path") and os.path.exists(doc["file_path"]):
        file_path = Path(doc["file_path"])
    else:
        # Match from uploads directory
        matches = list(settings.uploads_path.glob(f"*_{doc['filename']}")) + list(settings.uploads_path.glob(doc["filename"]))
        if matches:
            file_path = matches[0]
            store.update_document_file_path(document_id, str(file_path))

    if not file_path or not file_path.exists():
        raise HTTPException(status_code=404, detail="Physical document file not found on disk")

    ext = (doc.get("file_type") or "").lower()
    media_type = "application/pdf" if ext == "pdf" else "text/plain; charset=utf-8"

    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=doc["filename"],
        content_disposition_type="inline",
    )


@router.delete("/documents/{document_id}", response_model=DocumentDeleteResponse)
async def delete_document(document_id: str):
    """Delete a document and rebuild the FAISS index."""
    state = get_state()
    store = state["store"]
    embedding_service = state["embedding_service"]

    # Check if document exists
    doc = store.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Clean up physical file if present
    if doc.get("file_path") and os.path.exists(doc["file_path"]):
        try:
            os.remove(doc["file_path"])
        except Exception as e:
            logger.warning(f"Failed to remove file on disk: {e}")

    # Delete from SQLite (cascades to chunks)
    store.delete_document(document_id)

    # Rebuild FAISS index without the deleted chunks (preserving video chunks if present)
    remaining_ids, remaining_texts = store.get_all_active_chunks()
    embedding_service.rebuild_index(remaining_ids, remaining_texts)

    return DocumentDeleteResponse(
        message="Document deleted successfully",
        document_id=document_id,
    )


# ── Chat ──────────────────────────────────────────────────────────────────────

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Ask a question about uploaded sources."""
    state = get_state()
    rag_service = state.get("rag_service")
    store = state["store"]

    if not rag_service:
        raise HTTPException(
            status_code=503,
            detail="AI service is not available. Check that GEMINI_API_KEY is configured.",
        )

    # Validate document_id if provided
    if request.document_id:
        doc = store.get_document(request.document_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

    # Validate video_id if provided
    if request.video_id:
        vid = store.get_video(request.video_id)
        if not vid:
            raise HTTPException(status_code=404, detail="Video not found")

    try:
        result = rag_service.answer(
            question=request.question,
            document_id=request.document_id,
            video_id=request.video_id,
            source_mode=request.source_mode or "all",
            history=request.history,
        )

        return ChatResponse(
            answer=result["answer"],
            citations=[
                c if isinstance(c, Citation) else Citation(**c)
                for c in result["citations"]
            ],
            insufficient_context=result["insufficient_context"],
            latency_ms=result["latency_ms"],
        )

    except LLMServiceError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception("Chat failed")
        raise HTTPException(status_code=500, detail=f"Chat processing failed: {str(e)}")


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """Ask a question with real-time Server-Sent Events (SSE) token streaming."""
    state = get_state()
    rag_service = state.get("rag_service")
    store = state["store"]

    if not rag_service:
        raise HTTPException(
            status_code=503,
            detail="AI service is not available. Check that GEMINI_API_KEY is configured.",
        )

    # Validate document_id if provided
    if request.document_id:
        doc = store.get_document(request.document_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

    # Validate video_id if provided
    if request.video_id:
        vid = store.get_video(request.video_id)
        if not vid:
            raise HTTPException(status_code=404, detail="Video not found")

    async def event_generator():
        try:
            async for event in rag_service.answer_stream(
                question=request.question,
                document_id=request.document_id,
                video_id=request.video_id,
                source_mode=request.source_mode or "all",
                history=request.history,
            ):
                event_type = event.get("type", "message")
                data_str = json.dumps(event)
                yield f"event: {event_type}\ndata: {data_str}\n\n"
        except LLMServiceError as e:
            err_data = json.dumps({"error": str(e)})
            yield f"event: error\ndata: {err_data}\n\n"
        except Exception as e:
            logger.exception("Chat stream failed")
            err_data = json.dumps({"error": f"Stream processing failed: {str(e)}"})
            yield f"event: error\ndata: {err_data}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── Study Tools ───────────────────────────────────────────────────────────────


@router.post("/study-tools/summary", response_model=SummaryResponse)
async def generate_summary(request: StudyToolRequest):
    """Generate a summary of the selected document."""
    state = get_state()
    study_service = state.get("study_service")

    if not study_service:
        raise HTTPException(status_code=503, detail="AI service is not available.")

    try:
        result = study_service.generate_summary(request.document_id)
        return SummaryResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except LLMServiceError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/study-tools/video-summary", response_model=VideoSummaryResponse)
async def generate_video_summary(request: VideoSummaryRequest):
    """Generate a timestamped chapter-by-chapter summary of the ingested video."""
    state = get_state()
    study_service = state.get("study_service")

    if not study_service:
        raise HTTPException(status_code=503, detail="AI service is not available.")

    try:
        result = await asyncio.to_thread(
            study_service.generate_video_summary,
            request.video_id,
            force_refresh=request.force_refresh,
        )
        return VideoSummaryResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except LLMServiceError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/study-tools/mcqs", response_model=MCQResponse)
async def generate_mcqs(request: StudyToolRequest):
    """Generate multiple-choice questions from the selected document."""
    state = get_state()
    study_service = state.get("study_service")

    if not study_service:
        raise HTTPException(status_code=503, detail="AI service is not available.")

    try:
        result = study_service.generate_mcqs(request.document_id, request.num_items)
        return MCQResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except LLMServiceError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/study-tools/flashcards", response_model=FlashcardResponse)
async def generate_flashcards(request: StudyToolRequest):
    """Generate revision flashcards from the selected document."""
    state = get_state()
    study_service = state.get("study_service")

    if not study_service:
        raise HTTPException(status_code=503, detail="AI service is not available.")

    try:
        result = study_service.generate_flashcards(request.document_id, request.num_items)
        return FlashcardResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except LLMServiceError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/study-tools/viva", response_model=VivaResponse)
async def generate_viva(request: StudyToolRequest):
    """Generate viva preparation questions from the selected document."""
    state = get_state()
    study_service = state.get("study_service")

    if not study_service:
        raise HTTPException(status_code=503, detail="AI service is not available.")

    try:
        result = study_service.generate_viva(request.document_id, request.num_items)
        return VivaResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except LLMServiceError as e:
        raise HTTPException(status_code=503, detail=str(e))


# ── Video Knowledge Retrieval Endpoints ──────────────────────────────────────


@router.post("/videos/ingest", response_model=VideoIngestResponse)
async def ingest_video(request: VideoIngestRequest):
    """
    Ingest a YouTube educational video:
    Validates URL, fetches oEmbed metadata, extracts timestamped transcripts,
    chunks with 60-90s sliding window, persists to SQLite, and indexes in FAISS.
    """
    state = get_state()
    store = state["store"]
    embedding_service = state["embedding_service"]
    video_service = state.get("video_service") or VideoService(store, embedding_service)

    try:
        video, num_chunks = await video_service.ingest_video(request.url)
        return VideoIngestResponse(
            video=VideoMeta(**video),
            num_chunks=num_chunks,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except TranscriptUnavailableError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error ingesting video '{request.url}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to ingest video: {e}")


@router.get("/videos", response_model=VideoListResponse)
async def list_videos():
    """Retrieve all ingested educational videos."""
    state = get_state()
    store = state["store"]
    videos = store.get_all_videos()
    return VideoListResponse(videos=[VideoMeta(**v) for v in videos])


@router.get("/videos/{video_id}", response_model=VideoDetailResponse)
async def get_video(video_id: str):
    """Retrieve metadata and all timestamped transcript chunks for a video."""
    state = get_state()
    store = state["store"]
    video = store.get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    raw_chunks = store.get_video_chunks(video_id)
    chunks = [
        VideoChunkMeta(
            id=c["id"],
            video_id=c["video_id"],
            chunk_index=c["chunk_index"],
            start_time=c["start_time"],
            end_time=c["end_time"],
            text=c["text"],
            timestamp_url=f"https://www.youtube.com/watch?v={video['youtube_id']}&t={int(c['start_time'])}s",
        )
        for c in raw_chunks
    ]

    return VideoDetailResponse(video=VideoMeta(**video), chunks=chunks)


@router.delete("/videos/{video_id}", response_model=VideoDeleteResponse)
async def delete_video(video_id: str):
    """Delete a video, its chunks, and rebuild the vector index."""
    state = get_state()
    store = state["store"]
    embedding_service = state["embedding_service"]
    video_service = state.get("video_service") or VideoService(store, embedding_service)

    video = store.get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    video_service.delete_video(video_id)

    # Rebuild FAISS index with remaining active chunks
    remaining_ids, remaining_texts = store.get_all_active_chunks()
    embedding_service.rebuild_index(remaining_ids, remaining_texts)

    return VideoDeleteResponse(
        message="Video deleted successfully",
        video_id=video_id,
    )


@router.post("/videos/search", response_model=VideoSearchResponse)
async def search_videos(request: VideoSearchRequest):
    """
    Perform semantic search specifically over ingested video transcripts,
    returning matching segments with verified YouTube timestamp links.
    """
    state = get_state()
    retrieval_service = state["retrieval_service"]

    retrieved = await retrieval_service.retrieve_video_async(
        query=request.query,
        top_k=request.top_k,
        video_id=request.video_id,
        threshold=request.threshold,
    )

    results = []
    for r in retrieved:
        if r.source_type == "video":
            results.append(
                VideoSearchResult(
                    chunk_id=r.chunk_id,
                    video_id=r.video_id or "",
                    video_title=r.video_title or "",
                    channel=r.channel,
                    start_time=r.start_time or 0.0,
                    end_time=r.end_time or 0.0,
                    timestamp_url=r.timestamp_url or "",
                    text=r.text,
                    score=r.score,
                )
            )

    return VideoSearchResponse(results=results)


@router.post("/documents/{document_id}/suggest-videos", response_model=VideoSuggestionsResponse)
async def suggest_videos_for_document(document_id: str):
    """
    Analyze an uploaded document and generate 3 to 5 targeted educational
    video lecture search recommendations with 1-click YouTube search links.
    """
    state = get_state()
    store = state["store"]
    llm_service = state.get("llm_service")

    doc = store.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if not llm_service:
        raise HTTPException(status_code=503, detail="Gemini is not configured")

    # Sample representative chunks from the document
    chunks = store.get_chunks_by_document(document_id)
    if not chunks:
        raise HTTPException(status_code=404, detail="Document has no content")

    # Sample up to first 8 chunks
    sample_text = "\n\n".join(c["text"] for c in chunks[:8])
    if len(sample_text) > 8000:
        sample_text = sample_text[:8000]

    prompt = f"""You are an expert academic curriculum advisor.
Given the following excerpt from the study document '{doc['filename']}', identify the core educational concepts and generate 3 to 5 targeted YouTube search recommendations for university-level video lectures (such as MIT OpenCourseWare, Stanford Online, 3Blue1Brown, Khan Academy, Crash Course).

Document Excerpt:
\"\"\"{sample_text}\"\"\"

Return ONLY valid JSON matching this exact structure:
{{
  "suggestions": [
    {{
      "title": "Exact suggested search phrase (e.g., MIT 18.06 Linear Algebra Eigenvalues)",
      "topic": "Concept covered in the document",
      "search_url": "https://www.youtube.com/results?search_query=...",
      "rationale": "One brief sentence explaining why this video topic reinforces the document."
    }}
  ]
}}
Ensure the 'search_url' contains properly url-encoded query parameters for YouTube search."""

    try:
        response_json = llm_service.generate_json(prompt)
        suggestions_data = response_json.get("suggestions", [])
        suggestions = [VideoSuggestion(**s) for s in suggestions_data]
        return VideoSuggestionsResponse(
            document_id=document_id,
            document_name=doc["filename"],
            suggestions=suggestions,
        )
    except Exception as e:
        logger.error(f"Failed to generate video suggestions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate video suggestions: {e}")


@router.get("/documents/{document_id}/video-recommendations", response_model=VideoRecommendationResponse)
async def get_video_recommendations(document_id: str, force_refresh: bool = False):
    """
    Get hybrid video recommendations for a document:
    1. From Your Library: Semantic FAISS matches across ingested video transcripts.
    2. Curated External: Targeted YouTube university lectures via Gemini.
    Cached in SQLite study_cache for instant <15ms retrieval.
    """
    state = get_state()
    store = state["store"]
    doc = store.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    study_service = state.get("study_service")
    if not study_service:
        raise HTTPException(status_code=503, detail="Gemini is not configured")

    try:
        rec = await asyncio.to_thread(
            study_service.generate_video_recommendations,
            document_id=document_id,
            force_refresh=force_refresh,
        )
        return VideoRecommendationResponse(**rec)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to generate video recommendations: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate video recommendations: {e}")
