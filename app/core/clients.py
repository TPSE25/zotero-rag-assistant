import logging
import os

import chromadb
from chromadb.api.models.Collection import Collection
from ollama import AsyncClient

from core.settings import EMBEDDING_MODEL


def create_ollama_client() -> AsyncClient:
    return AsyncClient(host=os.getenv("OLLAMA_BASE_URL"))


def create_chroma_client() -> chromadb.ClientAPI:
    host = os.getenv("CHROMA_HOST", "localhost")
    port = int(os.getenv("CHROMA_PORT", "8000"))
    return chromadb.HttpClient(host=host, port=port)


def get_or_create_chroma_collection() -> Collection:
    chroma_client = create_chroma_client()
    collection = chroma_client.get_or_create_collection("embeddings")

    if collection.metadata is None or "embedding_model" not in collection.metadata:
        collection.modify(metadata={"embedding_model": EMBEDDING_MODEL})
        logging.info(f"Stored embedding model name: {EMBEDDING_MODEL}")
    elif collection.metadata.get("embedding_model") != EMBEDDING_MODEL:
        old_model = collection.metadata.get("embedding_model")
        logging.error(f"Embedding model changed from {old_model} to {EMBEDDING_MODEL}")
        raise ValueError(
            f"Embedding model changed from {old_model} to {EMBEDDING_MODEL}. "
            "Please reset the collection before changing models."
        )

    return collection


async def ensure_model_installed(model_name: str) -> bool:
    try:
        client = create_ollama_client()
        resp = await client.list()
        installed_models = [m.model for m in resp.models if m.model is not None]

        if model_name in installed_models:
            logging.info(f"Model {model_name} is already installed")
            return True

        logging.info(f"Model {model_name} not found, installing...")
        await client.pull(model=model_name)
        logging.info(f"Successfully installed model {model_name}")
        return True
    except Exception as e:
        logging.error(f"Failed to install model {model_name}: {e}")
        return False
