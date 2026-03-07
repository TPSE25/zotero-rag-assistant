from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

from core.clients import create_ollama_client, get_or_create_chroma_collection

router = APIRouter(tags=["health"])


@router.get("/api/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


@router.get("/api/ollama-list-models")
async def ollama_list() -> List[str]:
    try:
        client = create_ollama_client()
        resp = await client.list()
        return [m.model for m in resp.models if m.model is not None]
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Ollama unreachable: {e!s}") from e


@router.get("/api/chroma-stats")
async def chroma_stats() -> Dict[str, Any]:
    try:
        collection = get_or_create_chroma_collection()
        return {
            "name": collection.name,
            "count": collection.count(),
            "metadata": collection.metadata,
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Chroma unreachable: {e!s}") from e
