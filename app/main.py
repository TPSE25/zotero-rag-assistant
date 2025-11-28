import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from ollama import AsyncClient

app = FastAPI()

class EchoIn(BaseModel):
    message: str

@app.get("/api/health")
async def health():
    return {"status": "ok"}

@app.post("/api/echo")
async def echo(body: EchoIn):
    return {"you_said": body.message}


def _create_ollama_client() -> AsyncClient:
    return AsyncClient(host=os.getenv("OLLAMA_BASE_URL"))

@app.get("/api/ollama-list-models")
async def ollama_health():
    try:
        client = _create_ollama_client()
        resp = await client.list()
        return [m.model for m in resp.models]
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Ollama unreachable: {e!s}") from e
