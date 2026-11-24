"""
Video Service: YouTube ingestion, metadata fetching, transcript extraction, and time-based chunking.
"""

import asyncio
import logging
import re
from typing import Optional
from urllib.parse import parse_qs, urlparse

import httpx
from youtube_transcript_api import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
    YouTubeTranscriptApi,
)

from app.services.embeddings import EmbeddingService
from app.services.store import StoreService

logger = logging.getLogger(__name__)


class TranscriptUnavailableError(Exception):
    """Raised when YouTube captions/transcripts cannot be retrieved."""
    pass


class VideoService:
    """Manages YouTube video discovery, ingestion, transcript parsing, and chunking."""

    def __init__(
        self,
        store: StoreService,
        embedding_service: EmbeddingService,
        llm_service: Optional[any] = None,
    ):
        self.store = store
        self.embedding_service = embedding_service
        self.llm_service = llm_service

    @staticmethod
    def extract_youtube_id(url: str) -> Optional[str]:
        """
        Extract the 11-character YouTube video ID from various URL formats.
        Supports:
          - https://www.youtube.com/watch?v=ID
          - https://youtube.com/watch?v=ID
          - https://youtu.be/ID
          - https://www.youtube.com/embed/ID
          - https://www.youtube.com/shorts/ID
          - Raw 11-character ID
        """
        if not url or not isinstance(url, str):
            return None

        clean_url = url.strip()

        # If user passed a bare 11-char ID
        if re.match(r"^[0-9A-Za-z_-]{11}$", clean_url):
            return clean_url

        try:
            parsed = urlparse(clean_url)
        except Exception:
            return None

        # youtu.be/ID
        if "youtu.be" in parsed.netloc:
            path_parts = parsed.path.strip("/").split("/")
            if path_parts and len(path_parts[0]) == 11:
                return path_parts[0]

        # youtube.com
        if "youtube.com" in parsed.netloc:
            # /watch?v=ID
            if parsed.path == "/watch" or parsed.path == "/watch/":
                qs = parse_qs(parsed.query)
                if "v" in qs and qs["v"] and len(qs["v"][0]) == 11:
                    return qs["v"][0]

            # /embed/ID or /shorts/ID or /v/ID
            for prefix in ("/embed/", "/shorts/", "/v/"):
                if parsed.path.startswith(prefix):
                    parts = parsed.path[len(prefix):].split("/")
                    if parts and len(parts[0]) == 11:
                        return parts[0]

        # Fallback regex search
        match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11})(?:\?|&|\/|$)", clean_url)
        if match:
            return match.group(1)

        return None

    async def fetch_metadata(self, youtube_id: str) -> dict:
        """
        Fetch video title, author, thumbnail, exact duration, and description chapters.
        Combines oEmbed service and watch page scraping for zero API key requirements.
        """
        watch_url = f"https://www.youtube.com/watch?v={youtube_id}"
        oembed_url = f"https://www.youtube.com/oembed?url={watch_url}&format=json"

        title = f"YouTube Video ({youtube_id})"
        channel = "YouTube"
        thumbnail_url = f"https://img.youtube.com/vi/{youtube_id}/hqdefault.jpg"
        duration: Optional[int] = None
        chapters: list[dict] = []

        # 1. Fetch basic metadata via oEmbed
        try:
            async with httpx.AsyncClient(timeout=6.0) as client:
                resp = await client.get(oembed_url, headers={"User-Agent": "IntelliNotes/3.2"})
                if resp.status_code == 200:
                    data = resp.json()
                    title = data.get("title", title)
                    channel = data.get("author_name", channel)
                    thumbnail_url = data.get("thumbnail_url", thumbnail_url)
        except Exception as e:
            logger.warning(f"Failed to fetch oEmbed metadata for {youtube_id}: {e}")

        # 2. Scrape watch page for exact duration and creator chapters
        try:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "en-US,en;q=0.9",
            }
            async with httpx.AsyncClient(timeout=6.0, follow_redirects=True) as client:
                resp = await client.get(watch_url, headers=headers)
                if resp.status_code == 200:
                    # Extract lengthSeconds
                    m_len = re.search(r'"lengthSeconds":"(\d+)"', resp.text)
                    if m_len:
                        duration = int(m_len.group(1))

                    # Extract creator chapters from description
                    desc_match = re.search(r'"shortDescription":"(.*?)(?<!\\)"', resp.text)
                    if desc_match:
                        raw_desc = desc_match.group(1).encode("utf-8").decode("unicode_escape", errors="ignore")
                        ts_regex = re.compile(r'(?:(?:(\d{1,2}):)?(\d{1,2}):(\d{2}))\s*[-–—:]?\s*([^\r\n]+)')
                        for match in ts_regex.finditer(raw_desc):
                            h, m, s, topic = match.groups()
                            sec = int(s) + int(m) * 60 + (int(h) * 3600 if h else 0)
                            if duration and sec > duration:
                                continue
                            formatted = f"{int(m):02d}:{int(s):02d}" if not h else f"{int(h):02d}:{int(m):02d}:{int(s):02d}"
                            clean_topic = topic.strip().strip("-–—: ")
                            if clean_topic and len(clean_topic) > 2:
                                chapters.append({
                                    "time_seconds": sec,
                                    "timestamp_formatted": formatted,
                                    "topic": clean_topic[:80],
                                    "description": f"Chapter: {clean_topic[:80]}",
                                })
        except Exception as e:
            logger.warning(f"Failed to scrape watch page metadata for {youtube_id}: {e}")

        return {
            "title": title,
            "channel": channel,
            "thumbnail_url": thumbnail_url,
            "url": watch_url,
            "duration": duration,
            "chapters": chapters,
        }

    def fetch_transcript(self, youtube_id: str) -> list[dict]:
        """
        Acquire video transcript via youtube-transcript-api.
        Tries common languages (English, Hindi, Spanish, etc.), falling back to auto-generated transcripts.
        Raises TranscriptUnavailableError if captions cannot be found on YouTube.
        """
        languages = [
            "en", "en-US", "en-GB",
            "hi", "es", "fr", "de", "pt", "ru", "ja", "ko", "zh", "it",
            "ar", "bn", "mr", "ta", "te", "gu", "kn", "ml", "pa", "ur",
        ]
        try:
            if hasattr(YouTubeTranscriptApi, "get_transcript"):
                return YouTubeTranscriptApi.get_transcript(youtube_id, languages=languages)
            else:
                api = YouTubeTranscriptApi()
                fetched = api.fetch(youtube_id, languages=languages)
                if hasattr(fetched, "to_raw_data"):
                    return fetched.to_raw_data()
                return [dict(x) for x in fetched]
        except (TranscriptsDisabled, NoTranscriptFound, VideoUnavailable) as e:
            logger.warning(f"Transcript unavailable for {youtube_id}: {e}")
            raise TranscriptUnavailableError(
                f"Captions or transcripts are unavailable or disabled for video '{youtube_id}'."
            ) from e
        except Exception as e:
            logger.error(f"Unexpected error retrieving transcript for {youtube_id}: {e}")
            raise TranscriptUnavailableError(
                f"Could not retrieve transcript for video '{youtube_id}': {e}"
            ) from e

    async def _generate_ai_video_content(
        self, youtube_id: str, meta: dict, duration_sec: Optional[int] = None
    ) -> tuple[list[dict], Optional[dict]]:
        """
        Multimodal AI fallback: Analyze video directly via Gemini when subtitles/captions
        are unavailable or disabled.
        Extracts key chronological content segments for RAG and structured timestamped summary.
        """
        if not self.llm_service:
            # Minimal fallback if LLM service is not configured
            title = meta.get("title", "Lecture Video")
            channel = meta.get("channel", "YouTube")
            dur = duration_sec or 60.0
            return [
                {
                    "start": 0.0,
                    "duration": float(dur),
                    "text": f"Lecture video '{title}' by {channel}. Educational video content.",
                }
            ], None

        dur_instruction = ""
        if duration_sec:
            dur_m = duration_sec // 60
            dur_s = duration_sec % 60
            dur_instruction = f"\nExact Video Duration: {dur_m:02d}:{dur_s:02d} ({duration_sec} seconds). All timestamps must be strictly bounded between 00:00 and {dur_m:02d}:{dur_s:02d}."

        prompt = f"""You are an expert academic video analyst.
Analyze this YouTube video: https://www.youtube.com/watch?v={youtube_id}
Title: {meta.get('title', 'Video')}
Channel: {meta.get('channel', 'YouTube')}{dur_instruction}

Extract comprehensive structured study notes and timestamped chapters from the video.
Return JSON with this exact schema:
{{
  "summary": "Detailed markdown study notes with key concepts, mathematical explanations if applicable, and takeaways",
  "timestamps": [
    {{
      "time_seconds": 0,
      "timestamp_formatted": "00:00",
      "topic": "Chapter Title",
      "description": "Clear explanation of what is presented in this section"
    }}
  ],
  "segments": [
    {{
      "start": 0.0,
      "duration": 45.0,
      "text": "Detailed factual content and concepts discussed in this section of the video"
    }}
  ]
}}
Provide at least 4 to 8 chronological segments representing the main concepts taught in the video so students can search and retrieve them with RAG."""

        try:
            data = await asyncio.to_thread(
                self.llm_service.generate_json,
                prompt,
                system_instruction="You are an expert video lecture analyst. Return valid JSON only.",
                temperature=0.2,
                max_output_tokens=3000,
            )

            segments = []
            if isinstance(data, dict) and isinstance(data.get("segments"), list):
                for s in data["segments"]:
                    if isinstance(s, dict) and "text" in s:
                        segments.append({
                            "start": float(s.get("start", 0.0)),
                            "duration": float(s.get("duration", 45.0)),
                            "text": str(s["text"]),
                        })

            if not segments:
                title = meta.get("title", "Lecture Video")
                channel = meta.get("channel", "YouTube")
                summary_snippet = data.get("summary", "")[:300] if isinstance(data, dict) else ""
                segments = [
                    {
                        "start": 0.0,
                        "duration": 60.0,
                        "text": f"Lecture video '{title}' by {channel}. {summary_snippet}",
                    }
                ]

            return segments, data
        except Exception as e:
            logger.warning(f"Gemini video analysis fallback error for {youtube_id}: {e}")
            title = meta.get("title", "Lecture Video")
            channel = meta.get("channel", "YouTube")
            return [
                {
                    "start": 0.0,
                    "duration": 60.0,
                    "text": f"Lecture video '{title}' by {channel}. Educational study content.",
                }
            ], None

    @staticmethod
    def chunk_transcript(
        transcript: list[dict],
        target_duration: float = 75.0,
        overlap_duration: float = 15.0,
    ) -> list[dict]:
        """
        Chunk transcript snippets using a time-based sliding window.
        
        Args:
            transcript: List of raw transcript segments with 'text', 'start', 'duration'.
            target_duration: Target duration in seconds for each chunk (default ~75s).
            overlap_duration: Overlap duration in seconds between consecutive chunks (default 15s).

        Returns:
            List of chunk dicts: {start_time, end_time, text, token_count}.
        """
        if not transcript:
            return []

        # Calculate total video duration
        last_seg = transcript[-1]
        total_duration = float(last_seg.get("start", 0.0)) + float(last_seg.get("duration", 0.0))

        # If transcript is shorter than target duration, return as a single chunk
        if total_duration <= target_duration:
            combined_text = " ".join(seg.get("text", "").strip() for seg in transcript if seg.get("text"))
            return [
                {
                    "start_time": round(float(transcript[0].get("start", 0.0)), 2),
                    "end_time": round(total_duration, 2),
                    "text": combined_text,
                    "token_count": len(combined_text.split()),
                }
            ]

        chunks = []
        step_duration = max(15.0, target_duration - overlap_duration)
        current_window_start = 0.0

        while current_window_start < total_duration:
            current_window_end = current_window_start + target_duration

            # Find all segments that overlap with [current_window_start, current_window_end]
            matching_segments = []
            for seg in transcript:
                seg_start = float(seg.get("start", 0.0))
                seg_end = seg_start + float(seg.get("duration", 0.0))

                # Segment falls within or overlaps window
                if seg_end >= current_window_start and seg_start <= current_window_end:
                    matching_segments.append(seg)

            if matching_segments:
                chunk_start = float(matching_segments[0].get("start", current_window_start))
                last_m = matching_segments[-1]
                chunk_end = float(last_m.get("start", 0.0)) + float(last_m.get("duration", 0.0))
                
                texts = [s.get("text", "").strip() for s in matching_segments if s.get("text", "").strip()]
                clean_text = " ".join(texts)

                if clean_text:
                    chunks.append(
                        {
                            "start_time": round(chunk_start, 2),
                            "end_time": round(chunk_end, 2),
                            "text": clean_text,
                            "token_count": len(clean_text.split()),
                        }
                    )

            current_window_start += step_duration

            # If we've reached or passed the end of the video, break
            if current_window_start >= total_duration - 5.0:
                break

        return chunks

    async def ingest_video(self, url: str) -> tuple[dict, int]:
        """
        Orchestrate video ingestion:
          1. Extract and validate YouTube ID.
          2. Deduplicate against existing video in SQLite.
          3. Fetch oEmbed metadata.
          4. Fetch transcript with youtube-transcript-api.
          5. Chunk transcript with time-based sliding window.
          6. Persist to SQLite (videos & video_chunks).
          7. Co-index chunks into FAISS vector space.
          8. Return (video_dict, num_chunks).
        """
        youtube_id = self.extract_youtube_id(url)
        if not youtube_id:
            raise ValueError(f"Invalid YouTube URL or ID: '{url}'")

        # Deduplication check
        existing = self.store.get_video_by_youtube_id(youtube_id)
        if existing:
            logger.info(f"Video {youtube_id} already ingested. Returning existing record.")
            return existing, existing.get("num_chunks", 0)

        # 1. Fetch metadata
        meta = await self.fetch_metadata(youtube_id)

        # 2. Fetch transcript (offload CPU/network block to threadpool)
        transcript = []
        transcript_err = None
        try:
            transcript = await asyncio.to_thread(self.fetch_transcript, youtube_id)
        except TranscriptUnavailableError as e:
            transcript_err = e

        ai_summary_data = None

        # 3. If no subtitles exist, use Gemini AI multimodal analysis if available
        if not transcript:
            if self.llm_service:
                logger.info(
                    f"No subtitle tracks on YouTube for '{meta['title']}' ({youtube_id}). Analyzing video via Gemini..."
                )
                transcript, ai_summary_data = await self._generate_ai_video_content(
                    youtube_id, meta, duration_sec=meta.get("duration")
                )
            elif transcript_err:
                raise transcript_err
            else:
                raise TranscriptUnavailableError(
                    f"Captions or transcripts are unavailable or disabled for video '{youtube_id}'."
                )

        # 4. Chunk transcript with optimal time windows
        chunks = self.chunk_transcript(transcript, target_duration=90.0, overlap_duration=15.0)
        if not chunks:
            # Resilient fallback chunk
            chunks = [
                {
                    "start_time": 0.0,
                    "end_time": float(meta.get("duration") or 60.0),
                    "text": f"Educational lecture video '{meta['title']}' by channel '{meta['channel']}'.",
                    "token_count": 15,
                }
            ]

        # Use exact metadata duration if available, falling back to chunk end times
        duration_sec = meta.get("duration") or (int(chunks[-1]["end_time"]) if chunks else 60)

        # 5. Save video record in SQLite
        video = self.store.create_video(
            youtube_id=youtube_id,
            url=meta["url"],
            title=meta["title"],
            channel=meta["channel"],
            duration=duration_sec,
            thumbnail_url=meta["thumbnail_url"],
        )

        # 6. Save video chunks in SQLite
        chunk_ids = self.store.store_video_chunks(video["id"], chunks)

        # 7. Embed and index video chunks in FAISS
        chunk_texts = [c["text"] for c in chunks]
        await asyncio.to_thread(self.embedding_service.add_chunks, chunk_ids, chunk_texts)

        # 8. Pre-cache verified creator chapters or AI summary for instant UI load
        if meta.get("chapters"):
            try:
                summary_payload = {
                    "video_id": video["id"],
                    "youtube_id": youtube_id,
                    "video_title": video["title"],
                    "channel": video.get("channel"),
                    "summary": f"## Overview of {video['title']}\n\nComprehensive study guide and timestamped chapter breakdown for {video['title']} by {video.get('channel') or 'YouTube'}.",
                    "timestamps": meta["chapters"],
                }
                self.store.set_video_cache(video["id"], "video_summary", summary_payload, 0)
                logger.info(f"Pre-cached {len(meta['chapters'])} creator chapters for video {video['id']}")
            except Exception as e:
                logger.warning(f"Could not pre-cache video creator chapters: {e}")
        elif ai_summary_data and isinstance(ai_summary_data, dict):
            try:
                summary_payload = {
                    "video_id": video["id"],
                    "youtube_id": youtube_id,
                    "video_title": video["title"],
                    "channel": video.get("channel"),
                    "summary": ai_summary_data.get("summary", f"Study notes for {video['title']}."),
                    "timestamps": ai_summary_data.get("timestamps", []),
                }
                self.store.set_video_cache(video["id"], "video_summary", summary_payload, 0)
                logger.info(f"Pre-cached AI timestamped summary for video {video['id']}")
            except Exception as e:
                logger.warning(f"Could not pre-cache video summary: {e}")

        logger.info(
            f"Successfully ingested video '{meta['title']}' ({youtube_id}) with {len(chunk_ids)} chunks."
        )
        video["num_chunks"] = len(chunk_ids)
        return video, len(chunk_ids)

    def delete_video(self, video_id: str) -> bool:
        """
        Delete video, its chunks, and remove vectors from FAISS.
        """
        video = self.store.get_video(video_id)
        if not video:
            return False

        chunks = self.store.get_video_chunks(video_id)
        chunk_ids_to_remove = {c["id"] for c in chunks}

        # Delete from SQLite (cascading)
        deleted = self.store.delete_video(video_id)

        # Remove from FAISS index
        if chunk_ids_to_remove:
            self.embedding_service.remove_chunks(chunk_ids_to_remove)

        return deleted
