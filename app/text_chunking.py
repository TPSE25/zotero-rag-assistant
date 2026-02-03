from typing import List, Union
import re

class TextChunker:
    """Splits long text into manageable chunks for embeddings."""

    def clean_text(self, text: Union[str, dict]) -> str:
        """
        Normalize and clean text.
        Accepts either a string or a dict of {filename: content}.
        Removes extra whitespace and line number artifacts.
        """
        if isinstance(text, dict):
            text = " ".join(text.values())
        # Remove line numbers pattern (number followed by space and number)
        text = re.sub(r'\b\d+\s+\d+\b', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def estimate_token_count(self, text: str) -> int:
        """
        Rough token estimation.
        Assumes 1 token ≈ 0.75 words.
        """
        words = text.split()
        return int(len(words) / 0.75)

    def chunk_text(self, text: str, max_tokens: int = 512, overlap_tokens: int = 50) -> List[str]:
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
        # Split into sentences
        sentences = re.split(r'(?<=[.!?])\s+', text)

        chunks: List[str] = []
        current_chunk: List[str] = []
        current_tokens = 0

        for sentence in sentences:
            sentence_tokens = self.estimate_token_count(sentence)

            # If adding this sentence exceeds max, save current chunk
            if current_tokens + sentence_tokens > max_tokens and current_chunk:
                chunks.append(' '.join(current_chunk))

                # Keep last few sentences for overlap
                overlap_sentences = []
                overlap_tokens_count = 0
                for s in reversed(current_chunk):
                    s_tokens = self.estimate_token_count(s)
                    if overlap_tokens_count + s_tokens <= overlap_tokens:
                        overlap_sentences.insert(0, s)
                        overlap_tokens_count += s_tokens
                    else:
                        break

                current_chunk = overlap_sentences
                current_tokens = overlap_tokens_count

            current_chunk.append(sentence)
            current_tokens += sentence_tokens

        # Add final chunk
        if current_chunk:
            chunks.append(' '.join(current_chunk))

        return chunks