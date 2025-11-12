import os
from typing import Optional
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
import httpx

app = FastAPI(title="Dummy REST API", version="0.1.0")

class EchoIn(BaseModel):
    message: str

@app.get("/api/health")
async def health():
    return {"status": "ok"}

@app.post("/api/echo")
async def echo(body: EchoIn):
    return {"you_said": body.message}


OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "not-provided")
HTTP_TIMEOUT = 800.0

_client: Optional[httpx.AsyncClient] = None

@app.on_event("startup")
async def _startup():
    global _client
    _client = httpx.AsyncClient(base_url=OLLAMA_BASE_URL, timeout=HTTP_TIMEOUT)

@app.on_event("shutdown")
async def _shutdown():
    global _client
    if _client:
        await _client.aclose()

@app.get("/api/ollama/health")
async def ollama_health():
    try:
        r = await _client.get("/api/tags")
        r.raise_for_status()
        data = r.json()
        return {"status": "ok", "models": [m.get("name") for m in data.get("models", [])]}
    except httpx.HTTPError as e:
        raise HTTPException(status_code=503, detail=f"Ollama unreachable at {OLLAMA_BASE_URL}: {e!s}")