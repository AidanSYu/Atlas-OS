"""Semantic chunking based on sentence boundaries and coherence.

Replaces fixed-size character chunking with intelligent splits that
respect paragraph and sentence boundaries, preventing mid-thought fragmentation.
"""
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

try:
    from semantic_text_splitter import TextSplitter
    SEMANTIC_SPLITTER_AVAILABLE = True
except ImportError:
    SEMANTIC_SPLITTER_AVAILABLE = False
    logger.info("semantic-text-splitter not installed - semantic chunking disabled")


class SemanticChunker:
    """Chunk text by semantic coherence instead of character count.

    Uses the Rust-based semantic-text-splitter which respects sentence
    and paragraph boundaries while targeting a token budget.
    """

    def __init__(self, max_tokens: int = 512):
        """
        Args:
            max_tokens: Target chunk size in tokens (not chars).
                        512 tokens ~ 380 words ~ 1900 chars.
        """
        self.max_tokens = max_tokens
        self._splitter = None

    def _ensure_splitter(self):
        """Lazy-load the splitter."""
        if self._splitter is not None:
            return

        if not SEMANTIC_SPLITTER_AVAILABLE:
            raise ImportError("semantic-text-splitter is not installed")

        # TextSplitter uses character capacity (approx 4 chars per token)
        capacity = self.max_tokens * 4
        self._splitter = TextSplitter(capacity=capacity)
        logger.info(f"Semantic splitter initialized (capacity={capacity} chars)")

    def chunk_text(
        self,
        text: str,
        page_number: int,
        doc_id: str,
        filename: str
    ) -> List[Dict[str, Any]]:
        """Split text into semantically coherent chunks.

        Args:
            text: The text to chunk
            page_number: Source page number
            doc_id: Parent document ID
            filename: Source filename

        Returns:
            List of chunk dicts with text, metadata, and positional info
        """
        self._ensure_splitter()

        chunks = []
        sections = self._splitter.chunks(text)

        start_char = 0
        for idx, section_text in enumerate(sections):
            section_text = section_text.strip()
            if not section_text:
                continue

            end_char = start_char + len(section_text)

            chunks.append({
                "text": section_text,
                "chunk_index": idx,
                "page_number": page_number,
                "start_char": start_char,
                "end_char": end_char,
                "metadata": {
                    "filename": filename,
                    "doc_id": doc_id,
                    "page": page_number,
                    "chunk_type": "semantic",
                }
            })

            # Advance past the section text in the original
            found_pos = text.find(section_text, start_char)
            if found_pos >= 0:
                start_char = found_pos + len(section_text)
            else:
                start_char = end_char

        return chunks

    def chunk_pages(
        self,
        pages: List[Dict[str, Any]],
        doc_id: str,
        filename: str
    ) -> List[Dict[str, Any]]:
        """Chunk all pages from a document.

        Args:
            pages: List of page dicts with 'text' and 'page_number'
            doc_id: Document ID
            filename: Source filename

        Returns:
            List of all chunks with sequential chunk_index
        """
        all_chunks = []
        global_idx = 0

        for page in pages:
            page_chunks = self.chunk_text(
                text=page["text"],
                page_number=page["page_number"],
                doc_id=doc_id,
                filename=filename,
            )
            # Re-index globally
            for chunk in page_chunks:
                chunk["chunk_index"] = global_idx
                global_idx += 1
                all_chunks.append(chunk)

        return all_chunks

    @classmethod
    def is_available(cls) -> bool:
        return SEMANTIC_SPLITTER_AVAILABLE
