from typing import List
import re

class TextChunker:
    """Splits long text into manageable chunks for embeddings."""

    def clean_text(self, text: str) -> str:
        """
        Normalize and clean text.
        Removes extra whitespace.
        """
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def estimate_token_count(self, text: str) -> int:
        """
        Rough token estimation.
        Assumes 1 token ≈ 0.75 words.
        """
        words = text.split()
        return int(len(words) / 0.75)

    def chunk_text(self, text: str, max_tokens: int = 512) -> List[str]:
        """
        Split text into chunks of max_tokens tokens.
        """
        words = text.split()
        chunks: List[str] = []
        current_chunk: List[str] = []

        for word in words:
            current_chunk.append(word)
            if self.estimate_token_count(' '.join(current_chunk)) >= max_tokens:
                # Remove the last word to stay within limit
                current_chunk.pop()
                chunks.append(' '.join(current_chunk))
                current_chunk = [word]

        if current_chunk:
            chunks.append(' '.join(current_chunk))

        return chunks
