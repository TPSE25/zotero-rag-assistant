import logging
import os
import sys
from typing import Dict, List, Any

from chromadb.api.models.Collection import Collection
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from ollama import AsyncClient
import chromadb

app = FastAPI()

logging.basicConfig(
    level=logging.INFO,
    handlers=[logging.StreamHandler(sys.stdout)],
)

class EchoIn(BaseModel):
    message: str

@app.get("/api/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}

@app.post("/api/echo")
async def echo(body: EchoIn) -> Dict[str, str]:
    return {"you_said": body.message}


def _create_ollama_client() -> AsyncClient:
    return AsyncClient(host=os.getenv("OLLAMA_BASE_URL"))

@app.get("/api/ollama-list-models")
async def ollama_list() -> List[str]:
    try:
        client = _create_ollama_client()
        resp = await client.list()
        return [m.model for m in resp.models if m.model is not None]
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Ollama unreachable: {e!s}") from e


def _create_chroma_client() -> chromadb.ClientAPI:
    host = os.getenv("CHROMA_HOST", "localhost")
    port = int(os.getenv("CHROMA_PORT", "8000"))
    return chromadb.HttpClient(host=host, port=port)

def _get_or_create_chroma_collection() -> Collection:
    chroma_client = _create_chroma_client()
    return chroma_client.get_or_create_collection("embeddings")

@app.get("/api/chroma-stats")
async def chroma_stats() -> Dict[str, Any]:
    try:
        collection = _get_or_create_chroma_collection()
        return {
            "name": collection.name,
            "count": collection.count(),
            "metadata": collection.metadata,
            "configuration": collection.configuration,
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Chroma unreachable: {e!s}") from e