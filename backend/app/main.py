"""
IntelliNotes FastAPI application entry point.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.api.routes import router, set_state
from app.services.store import StoreService
from app.services.embeddings import EmbeddingService
from app.services.retrieval import RetrievalService
from app.services.rag import RAGService
from app.services.llm import LLMService, LLMServiceError
from app.services.study import StudyService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize services on startup."""
    logger.info("Starting IntelliNotes backend...")

    settings = get_settings()

    # Initialize storage
    store = StoreService(settings.db_path)
    logger.info(f"SQLite database at: {settings.db_path}")

    # Initialize embedding service and FAISS index
    embedding_service = EmbeddingService(
        model_name=settings.EMBEDDING_MODEL,
        index_path=settings.index_path,
        chunk_map_path=settings.chunk_map_path,
    )
    logger.info(f"FAISS index loaded with {embedding_service.total_vectors} vectors")

    # Initialize retrieval service
    retrieval_service = RetrievalService(embedding_service, store)

    # Initialize LLM and RAG services (graceful if no API key)
    rag_service = None
    study_service = None

    if settings.GEMINI_API_KEY:
        try:
            llm_service = LLMService(settings.GEMINI_API_KEY, settings.GEMINI_MODEL)
            rag_service = RAGService(
                retrieval_service,
                llm_service,
                top_k=settings.TOP_K,
                similarity_threshold=settings.SIMILARITY_THRESHOLD,
            )
            study_service = StudyService(store, llm_service, retrieval=retrieval_service)
            logger.info(f"Gemini configured with model: {settings.GEMINI_MODEL}")
        except LLMServiceError as e:
            logger.warning(f"LLM service initialization failed: {e}")
    else:
        logger.warning("GEMINI_API_KEY not set. Chat and study tools will be unavailable.")

    # Initialize video service
    from app.services.video import VideoService
    video_service = VideoService(store, embedding_service, llm_service=llm_service if settings.GEMINI_API_KEY else None)

    # Set shared state for routes
    set_state({
        "settings": settings,
        "store": store,
        "embedding_service": embedding_service,
        "retrieval_service": retrieval_service,
        "rag_service": rag_service,
        "study_service": study_service,
        "video_service": video_service,
        "llm_service": llm_service if settings.GEMINI_API_KEY else None,
    })

    logger.info("IntelliNotes backend ready")
    yield
    logger.info("Shutting down IntelliNotes backend")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="IntelliNotes",
        description="AI-powered academic study assistant with RAG",
        version="1.0.0",
        lifespan=lifespan,
    )

    import os
    frontend_url = os.getenv("FRONTEND_URL")
    allowed_origins = [
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
    ]
    if frontend_url:
        allowed_origins.append(frontend_url.rstrip("/"))

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_origin_regex=r"^https:\/\/.*\.vercel\.app$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)

    return app


app = create_app()
# Reloaded model settings

