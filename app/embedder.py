import os
import logging
from typing import List
from ollama import AsyncClient


class EmbeddingService:
    async def embed_text(self, text: str, model: str = "llama3.2") -> List[float]:
        """
        Generate embedding for a single text using Ollama API.
        """
        client = AsyncClient(
            base_url=os.getenv("OLLAMA_API_URL", "http://localhost:11434")
        )

        try:
            response = await client.embed(model=model, input=text)
            return list(response.embeddings[0])
        except Exception as e:
            logging.error(f"Error generating embedding for text: {e}")
            return []

    async def embed_texts(
        self, texts: List[str], model: str = "llama3.2"
    ) -> List[List[float]]:
        """
        Generate embeddings for a list of texts using Ollama API.
        """
        client = AsyncClient(
            base_url=os.getenv("OLLAMA_API_URL", "http://localhost:11434")
        )

        try:
            response = await client.embed(model=model, input=texts)
            return [list(vec) for vec in response.embeddings]
        except Exception as e:
            logging.error(f"Error generating embeddings: {e}")
            return [[] for _ in texts]

    async def embed_chunks(
        self, chunks: List[str], model: str = "llama3.2"
    ) -> List[List[float]]:
        """
        Generate embeddings for a list of text chunks using Ollama API.
        """
        return await self.embed_texts(chunks, model)

    async def embed_health_check(self, model: str = "llama3.2") -> bool:
        """
        Perform a health check on the embedding service.
        """
        client = AsyncClient(
            base_url=os.getenv("OLLAMA_API_URL", "http://localhost:11434")
        )

        try:
            response = await client.embed(model=model, input="health check")
            return len(response.embeddings) > 0
        except Exception as e:
            logging.error(f"Health check failed: {e}")
            return False
