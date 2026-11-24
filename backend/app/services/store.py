"""
SQLite storage service for document and chunk metadata.
"""

import sqlite3
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.config import Settings


class StoreService:
    """Manages SQLite database for documents and chunks."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_db(self):
        conn = self._get_conn()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    file_type TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    num_chunks INTEGER NOT NULL DEFAULT 0,
                    num_pages INTEGER,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS chunks (
                    id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    page INTEGER,
                    start_char INTEGER,
                    end_char INTEGER,
                    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON chunks(document_id);

                CREATE TABLE IF NOT EXISTS study_cache (
                    id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    tool_type TEXT NOT NULL,
                    num_items INTEGER NOT NULL DEFAULT 0,
                    content_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
                    UNIQUE(document_id, tool_type, num_items)
                );

                CREATE INDEX IF NOT EXISTS idx_study_cache_doc ON study_cache(document_id, tool_type);

                CREATE TABLE IF NOT EXISTS videos (
                    id TEXT PRIMARY KEY,
                    youtube_id TEXT UNIQUE NOT NULL,
                    url TEXT NOT NULL,
                    title TEXT NOT NULL,
                    channel TEXT,
                    duration INTEGER,
                    thumbnail_url TEXT,
                    num_chunks INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_videos_youtube_id ON videos(youtube_id);

                CREATE TABLE IF NOT EXISTS video_chunks (
                    id TEXT PRIMARY KEY,
                    video_id TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    start_time REAL NOT NULL,
                    end_time REAL NOT NULL,
                    text TEXT NOT NULL,
                    token_count INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_video_chunks_video_id ON video_chunks(video_id);

                CREATE TABLE IF NOT EXISTS video_cache (
                    id TEXT PRIMARY KEY,
                    video_id TEXT NOT NULL,
                    tool_type TEXT NOT NULL,
                    num_items INTEGER NOT NULL DEFAULT 0,
                    content_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE,
                    UNIQUE(video_id, tool_type, num_items)
                );

                CREATE INDEX IF NOT EXISTS idx_video_cache_vid ON video_cache(video_id, tool_type);
            """)
            conn.commit()

            # Ensure file_path column exists for document serving
            try:
                conn.execute("ALTER TABLE documents ADD COLUMN file_path TEXT")
                conn.commit()
            except sqlite3.OperationalError:
                pass
        finally:
            conn.close()

    def create_document(
        self,
        filename: str,
        file_type: str,
        file_size: int,
        num_pages: Optional[int] = None,
        file_path: Optional[str] = None,
    ) -> dict:
        """Create a new document record and return its metadata."""
        doc_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        conn = self._get_conn()
        try:
            conn.execute(
                """INSERT INTO documents (id, filename, file_type, file_size, num_chunks, num_pages, created_at, file_path)
                   VALUES (?, ?, ?, ?, 0, ?, ?, ?)""",
                (doc_id, filename, file_type, file_size, num_pages, created_at, file_path),
            )
            conn.commit()
            return {
                "id": doc_id,
                "filename": filename,
                "file_type": file_type,
                "file_size": file_size,
                "num_chunks": 0,
                "num_pages": num_pages,
                "created_at": created_at,
                "file_path": file_path,
            }
        finally:
            conn.close()

    def update_document_file_path(self, document_id: str, file_path: str) -> None:
        """Update the stored file_path for a document."""
        conn = self._get_conn()
        try:
            conn.execute(
                "UPDATE documents SET file_path = ? WHERE id = ?",
                (file_path, document_id),
            )
            conn.commit()
        finally:
            conn.close()

    def store_chunks(self, document_id: str, chunks: list[dict]) -> list[str]:
        """Store text chunks for a document. Returns list of chunk IDs."""
        conn = self._get_conn()
        chunk_ids = []
        try:
            for i, chunk in enumerate(chunks):
                chunk_id = str(uuid.uuid4())
                chunk_ids.append(chunk_id)
                conn.execute(
                    """INSERT INTO chunks (id, document_id, chunk_index, text, page, start_char, end_char)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        chunk_id,
                        document_id,
                        i,
                        chunk["text"],
                        chunk.get("page"),
                        chunk.get("start_char"),
                        chunk.get("end_char"),
                    ),
                )
            # Update document chunk count
            conn.execute(
                "UPDATE documents SET num_chunks = ? WHERE id = ?",
                (len(chunks), document_id),
            )
            conn.commit()
            return chunk_ids
        finally:
            conn.close()

    def get_document(self, document_id: str) -> Optional[dict]:
        """Retrieve a document by ID."""
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM documents WHERE id = ?", (document_id,)
            ).fetchone()
            if row:
                return dict(row)
            return None
        finally:
            conn.close()

    def get_all_documents(self) -> list[dict]:
        """Retrieve all documents."""
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM documents ORDER BY created_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_chunks_by_document(self, document_id: str) -> list[dict]:
        """Retrieve all chunks for a document."""
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM chunks WHERE document_id = ? ORDER BY chunk_index",
                (document_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_chunks_by_ids(self, chunk_ids: list[str]) -> list[dict]:
        """Retrieve chunks by their IDs."""
        if not chunk_ids:
            return []
        conn = self._get_conn()
        try:
            placeholders = ",".join("?" for _ in chunk_ids)
            rows = conn.execute(
                f"SELECT * FROM chunks WHERE id IN ({placeholders})", chunk_ids
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_chunk(self, chunk_id: str) -> Optional[dict]:
        """Retrieve a single chunk by ID."""
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM chunks WHERE id = ?", (chunk_id,)
            ).fetchone()
            if row:
                return dict(row)
            return None
        finally:
            conn.close()

    def delete_document(self, document_id: str) -> bool:
        """Delete a document and its chunks. Returns True if deleted."""
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "DELETE FROM documents WHERE id = ?", (document_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def get_all_chunk_ids(self) -> list[str]:
        """Return all chunk IDs in the database, ordered by document and index."""
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT id FROM chunks ORDER BY document_id, chunk_index"
            ).fetchall()
            return [r["id"] for r in rows]
        finally:
            conn.close()

    def count_documents(self) -> int:
        """Return the total number of documents."""
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT COUNT(*) as cnt FROM documents").fetchone()
            return row["cnt"]
        finally:
            conn.close()

    def get_study_cache(self, document_id: str, tool_type: str, num_items: int = 0) -> Optional[dict]:
        """Retrieve cached study material if it exists."""
        conn = self._get_conn()
        try:
            row = conn.execute(
                """SELECT content_json FROM study_cache
                   WHERE document_id = ? AND tool_type = ? AND num_items = ?""",
                (document_id, tool_type, num_items),
            ).fetchone()
            if row:
                return json.loads(row["content_json"])
            return None
        finally:
            conn.close()

    def set_study_cache(self, document_id: str, tool_type: str, content: dict, num_items: int = 0):
        """Store or update generated study material in cache."""
        cache_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        content_json = json.dumps(content)
        conn = self._get_conn()
        try:
            conn.execute(
                """INSERT INTO study_cache (id, document_id, tool_type, num_items, content_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(document_id, tool_type, num_items)
                   DO UPDATE SET content_json = excluded.content_json, created_at = excluded.created_at""",
                (cache_id, document_id, tool_type, num_items, content_json, created_at),
            )
            conn.commit()
        finally:
            conn.close()

    def get_video_cache(self, video_id: str, tool_type: str, num_items: int = 0) -> Optional[dict]:
        """Retrieve cached video study content if available."""
        conn = self._get_conn()
        try:
            row = conn.execute(
                """SELECT content_json FROM video_cache
                   WHERE video_id = ? AND tool_type = ? AND num_items = ?""",
                (video_id, tool_type, num_items),
            ).fetchone()
            if row:
                return json.loads(row["content_json"])
            return None
        finally:
            conn.close()

    def set_video_cache(self, video_id: str, tool_type: str, content: dict, num_items: int = 0) -> None:
        """Store or update generated video study content in cache."""
        cache_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        content_json = json.dumps(content)
        conn = self._get_conn()
        try:
            conn.execute(
                """INSERT INTO video_cache (id, video_id, tool_type, num_items, content_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(video_id, tool_type, num_items)
                   DO UPDATE SET content_json = excluded.content_json, created_at = excluded.created_at""",
                (cache_id, video_id, tool_type, num_items, content_json, created_at),
            )
            conn.commit()
        finally:
            conn.close()

    # ==================== Video Storage & Retrieval ====================

    def create_video(
        self,
        youtube_id: str,
        url: str,
        title: str,
        channel: Optional[str] = None,
        duration: Optional[int] = None,
        thumbnail_url: Optional[str] = None,
    ) -> dict:
        """Create a new video record and return its metadata."""
        vid_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        conn = self._get_conn()
        try:
            conn.execute(
                """INSERT INTO videos (id, youtube_id, url, title, channel, duration, thumbnail_url, num_chunks, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)""",
                (vid_id, youtube_id, url, title, channel, duration, thumbnail_url, created_at),
            )
            conn.commit()
            return {
                "id": vid_id,
                "youtube_id": youtube_id,
                "url": url,
                "title": title,
                "channel": channel,
                "duration": duration,
                "thumbnail_url": thumbnail_url,
                "num_chunks": 0,
                "created_at": created_at,
            }
        finally:
            conn.close()

    def get_video(self, video_id: str) -> Optional[dict]:
        """Retrieve a video by ID."""
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM videos WHERE id = ?", (video_id,)
            ).fetchone()
            if row:
                return dict(row)
            return None
        finally:
            conn.close()

    def get_video_by_youtube_id(self, youtube_id: str) -> Optional[dict]:
        """Retrieve a video by its YouTube 11-char ID for deduplication."""
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM videos WHERE youtube_id = ?", (youtube_id,)
            ).fetchone()
            if row:
                return dict(row)
            return None
        finally:
            conn.close()

    def get_all_videos(self) -> list[dict]:
        """Retrieve all ingested videos ordered by created_at desc."""
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM videos ORDER BY created_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def store_video_chunks(self, video_id: str, chunks: list[dict]) -> list[str]:
        """Store transcript chunks for a video. Returns list of chunk IDs."""
        conn = self._get_conn()
        chunk_ids = []
        try:
            for i, chunk in enumerate(chunks):
                chunk_id = str(uuid.uuid4())
                chunk_ids.append(chunk_id)
                conn.execute(
                    """INSERT INTO video_chunks (id, video_id, chunk_index, start_time, end_time, text, token_count)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        chunk_id,
                        video_id,
                        i,
                        chunk["start_time"],
                        chunk["end_time"],
                        chunk["text"],
                        chunk.get("token_count", 0),
                    ),
                )
            conn.execute(
                "UPDATE videos SET num_chunks = ? WHERE id = ?",
                (len(chunks), video_id),
            )
            conn.commit()
            return chunk_ids
        finally:
            conn.close()

    def get_video_chunks(self, video_id: str) -> list[dict]:
        """Retrieve all chunks for a video ordered by chunk_index."""
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM video_chunks WHERE video_id = ? ORDER BY chunk_index",
                (video_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_video_chunk(self, chunk_id: str) -> Optional[dict]:
        """Retrieve a single video chunk by ID."""
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM video_chunks WHERE id = ?", (chunk_id,)
            ).fetchone()
            if row:
                return dict(row)
            return None
        finally:
            conn.close()

    def get_video_chunks_by_ids(self, chunk_ids: list[str]) -> list[dict]:
        """Retrieve video chunks by their IDs."""
        if not chunk_ids:
            return []
        conn = self._get_conn()
        try:
            placeholders = ",".join("?" for _ in chunk_ids)
            rows = conn.execute(
                f"SELECT * FROM video_chunks WHERE id IN ({placeholders})", chunk_ids
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def delete_video(self, video_id: str) -> bool:
        """Delete a video and its chunks (via CASCADE)."""
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "DELETE FROM videos WHERE id = ?", (video_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def count_videos(self) -> int:
        """Return total count of ingested videos."""
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT COUNT(*) as cnt FROM videos").fetchone()
            return row["cnt"]
        finally:
            conn.close()

    def get_all_video_chunk_ids(self) -> list[str]:
        """Return all video chunk IDs in database."""
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT id FROM video_chunks ORDER BY video_id, chunk_index"
            ).fetchall()
            return [r["id"] for r in rows]
        finally:
            conn.close()

    def get_chunks_by_ids_any(self, chunk_ids: list[str]) -> list[dict]:
        """
        Unified chunk lookup: fetches chunk details from either 'chunks' (document)
        or 'video_chunks' (video) and attaches source metadata.
        """
        if not chunk_ids:
            return []
        conn = self._get_conn()
        try:
            placeholders = ",".join("?" for _ in chunk_ids)
            # Query document chunks joined with documents for filename
            doc_rows = conn.execute(
                f"""SELECT c.id, c.document_id, c.chunk_index, c.text, c.page, d.filename as source_name
                    FROM chunks c
                    JOIN documents d ON c.document_id = d.id
                    WHERE c.id IN ({placeholders})""",
                chunk_ids,
            ).fetchall()

            # Query video chunks joined with videos for title, url, channel
            vid_rows = conn.execute(
                f"""SELECT vc.id, vc.video_id, vc.chunk_index, vc.start_time, vc.end_time, vc.text,
                           v.title as source_name, v.url, v.channel, v.youtube_id
                    FROM video_chunks vc
                    JOIN videos v ON vc.video_id = v.id
                    WHERE vc.id IN ({placeholders})""",
                chunk_ids,
            ).fetchall()

            results = []
            for r in doc_rows:
                item = dict(r)
                item["source_type"] = "document"
                results.append(item)
            for r in vid_rows:
                item = dict(r)
                item["source_type"] = "video"
                # Generate exact timestamp link
                start_sec = int(item["start_time"])
                item["timestamp_url"] = f"https://www.youtube.com/watch?v={item['youtube_id']}&t={start_sec}s"
                results.append(item)

            return results
        finally:
            conn.close()

    def get_all_active_chunks(self) -> tuple[list[str], list[str]]:
        """Return (chunk_ids, texts) for all active document chunks and video chunks."""
        conn = self._get_conn()
        try:
            doc_rows = conn.execute(
                "SELECT id, text FROM chunks ORDER BY document_id, chunk_index"
            ).fetchall()
            vid_rows = conn.execute(
                "SELECT id, text FROM video_chunks ORDER BY video_id, chunk_index"
            ).fetchall()
            all_ids = [r["id"] for r in doc_rows] + [r["id"] for r in vid_rows]
            all_texts = [r["text"] for r in doc_rows] + [r["text"] for r in vid_rows]
            return all_ids, all_texts
        finally:
            conn.close()

