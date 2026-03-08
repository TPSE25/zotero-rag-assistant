from typing import List, Union
import re


PAGE_MARKER_RE = re.compile(r"\[\[PAGE:(\d+)\]\]")

class TextChunker:
    """Splits long text into manageable chunks for embeddings."""

    def clean_text(self, text: Union[str, dict]) -> str:
        """
        Normalize and clean text.
        Accepts either a string or a dict of {filename: content}.
        Removes extra whitespace.
        """
        if isinstance(text, dict):
            text = " ".join(text.values())
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    def estimate_token_count(self, text: str) -> int:
        """
        Rough token estimation.
        Assumes 1 token ≈ 0.75 words.
        """
        words = text.split()
        return int(len(words) / 0.75)

    def chunk_text(self, text: str, max_tokens: int = 800, overlap_tokens: int = 50) -> List[str]:
        chunks_with_pages = self.chunk_text_with_pages(
            text,
            max_tokens=max_tokens,
            overlap_tokens=overlap_tokens,
        )
        return [chunk for chunk, _page_start, _page_end in chunks_with_pages]

    def chunk_text_with_pages(
        self,
        text: str,
        max_tokens: int = 800,
        overlap_tokens: int = 50,
    ) -> List[tuple[str, int | None, int | None]]:
        """
        Split text into chunks respecting sentence boundaries.
        Adds overlap for better context continuity in RAG retrieval.

        Args:
            text: Text to chunk
            max_tokens: Maximum tokens per chunk (approximate)
            overlap_tokens: Tokens to overlap between chunks for context

        Returns:
            List of text chunks
        """
        parts = re.split(r"(\[\[PAGE:\d+\]\])", text)
        units: List[tuple[str, int | None]] = []
        current_page: int | None = None
        for part in parts:
            if not part:
                continue
            marker = PAGE_MARKER_RE.fullmatch(part.strip())
            if marker:
                current_page = int(marker.group(1))
                continue
            for sentence in re.split(r'(?<=[.!?])\s+', part):
                sentence = sentence.strip()
                if sentence:
                    units.append((sentence, current_page))

        chunks: List[tuple[str, int | None, int | None]] = []
        current_chunk: List[tuple[str, int | None]] = []
        current_tokens = 0

        for sentence, page in units:
            sentence_tokens = self.estimate_token_count(sentence)

            # If adding this sentence exceeds max, save current chunk
            if current_tokens + sentence_tokens > max_tokens and current_chunk:
                chunk_pages = sorted({p for _s, p in current_chunk if p is not None})
                chunks.append(
                    (
                        ' '.join(s for s, _p in current_chunk),
                        chunk_pages[0] if chunk_pages else None,
                        chunk_pages[-1] if chunk_pages else None,
                    )
                )

                # Keep last few sentences for overlap
                overlap_sentences: List[tuple[str, int | None]] = []
                overlap_tokens_count = 0
                for s, p in reversed(current_chunk):
                    s_tokens = self.estimate_token_count(s)
                    if overlap_tokens_count + s_tokens <= overlap_tokens:
                        overlap_sentences.insert(0, (s, p))
                        overlap_tokens_count += s_tokens
                    else:
                        break

                current_chunk = overlap_sentences
                current_tokens = overlap_tokens_count

            current_chunk.append((sentence, page))
            current_tokens += sentence_tokens

        # Add final chunk
        if current_chunk:
            chunk_pages = sorted({p for _s, p in current_chunk if p is not None})
            chunks.append(
                (
                    ' '.join(s for s, _p in current_chunk),
                    chunk_pages[0] if chunk_pages else None,
                    chunk_pages[-1] if chunk_pages else None,
                )
            )

        return chunks
