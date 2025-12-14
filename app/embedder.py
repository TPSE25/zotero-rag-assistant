from typing import List
from ollama import AsyncClient
import os
import logging


class EmbeddingService:
   async def embed_text(self, text: str, model: str = "llama3.2") -> List[float]:
        """
        Generate embedding for a single text using Ollama API.
        """
        ollama_api_url = os.getenv("OLLAMA_API_URL", "http://localhost:11434")
        client = AsyncClient(base_url=ollama_api_url)

        try:
            response = await client.embed(model=model, input=text)
            return response.embedding
        except Exception as e:
            logging.error(f"Error generating embedding for text: {e}")
            return []
   async def embed_texts(self,texts:List[str],model:str="llama3.2")->List[List[float]]:
        """
        Generate embeddings for a list of texts using Ollama API.
        """
        ollama_api_url = os.getenv("OLLAMA_API_URL", "http://localhost:11434")
        client = AsyncClient(base_url=ollama_api_url)

        embeddings = []
        for text in texts:
            try:
                response = await client.embed(model=model, input=text)
                embeddings.append(response.embedding)
            except Exception as e:
                logging.error(f"Error generating embedding for text: {e}")
                embeddings.append([])
        return embeddings
   async def embed_chunks(self,chunks:List[str],model:str="llama3.2")->List[List[float]]:
        """
        Generate embeddings for a list of text chunks using Ollama API.
        """
        ollama_api_url = os.getenv("OLLAMA_API_URL", "http://localhost:11434")
        client = AsyncClient(base_url=ollama_api_url)

        embeddings = []
        for chunk in chunks:
            try:
                response = await client.embed(model=model, input=chunk)
                embeddings.append(response.embedding)
            except Exception as e:
                logging.error(f"Error generating embedding for chunk: {e}")
                embeddings.append([])
        return embeddings
   async def embed_health_check(self,model:str="llama3.2")->bool:
        """
        Perform a health check on the embedding service.
        """
        ollama_api_url = os.getenv("OLLAMA_API_URL", "http://localhost:11434")
        client = AsyncClient(base_url=ollama_api_url)

        try:
            response = await client.embed(model=model, input="health check")
            return True if response.embedding else False
        except Exception as e:
            logging.error(f"Health check failed: {e}")
            return False