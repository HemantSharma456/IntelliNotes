"""
Text chunking service with configurable size and overlap.
"""

from typing import Optional


def chunk_text(
    text: str,
    chunk_size: int = 512,
    chunk_overlap: int = 64,
    page_breaks: Optional[list[int]] = None,
) -> list[dict]:
    """
    Split text into overlapping chunks.

    Args:
        text: The full extracted text.
        chunk_size: Target chunk size in characters.
        chunk_overlap: Number of overlapping characters between chunks.
        page_breaks: List of character positions where new pages start (for PDFs).

    Returns:
        List of chunk dicts with keys: text, page, start_char, end_char.
    """
    if not text or not text.strip():
        return []

    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be less than chunk_size")

    chunks = []
    start = 0
    text_len = len(text)
    step = chunk_size - chunk_overlap

    while start < text_len:
        end = min(start + chunk_size, text_len)
        chunk_text_content = text[start:end]

        # Only include non-empty chunks
        if chunk_text_content.strip():
            # Determine page number from page_breaks
            page = _find_page(start, page_breaks)

            chunks.append({
                "text": chunk_text_content,
                "page": page,
                "start_char": start,
                "end_char": end,
            })

        start += step

    return chunks


def _find_page(char_pos: int, page_breaks: Optional[list[int]]) -> Optional[int]:
    """Find the page number for a given character position."""
    if not page_breaks:
        return None

    page = 1
    for break_pos in page_breaks:
        if char_pos >= break_pos:
            page += 1
        else:
            break
    return page
