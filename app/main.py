import logging
import os
import sys
import tempfile
from typing import Dict, List, Any

from chromadb.api.models.Collection import Collection
from fastapi import FastAPI, HTTPException, UploadFile, Form, File
from pydantic import BaseModel
from ollama import AsyncClient
import chromadb

from app.file_extractor import extract_auto
from app.text_chunking import TextChunker

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

class QueryIn(BaseModel):
    prompt: str

class Hit(BaseModel):
    text: str
    filename: str

class QueryOut(BaseModel):
    response: str
    sources: List[str]

async def get_query_hits(prompt: str, n_results: int = 5) -> List[Hit]:
    collection = _get_or_create_chroma_collection()
    client = _create_ollama_client()
    response = await client.embed(model="nomic-embed-text", input=prompt)
    embeddings = list(response.embeddings[0])
    res = collection.query(
        query_embeddings=[embeddings],
        n_results=n_results,
        include=["documents", "metadatas"],
    )
    return [
        Hit(text=document, filename=metadata.get("filename", "unknown"))
        for document, metadata in zip(res["documents"][0], res["metadatas"][0])
    ]

@app.post("/api/query")
async def query(body: QueryIn) -> QueryOut:
    hits = await get_query_hits(body.prompt)
    sources = list(set(hit.filename for hit in hits))
    context = "\n\n".join(hit.text for hit in hits)
    
    client = _create_ollama_client()
    enriched = f"{context}\n\n{body.prompt}" if context else body.prompt
    out = await client.generate(model="llama3.2:latest", prompt=enriched)
    return QueryOut(response=out.response, sources=sources)

@app.post("/internal/file-changed")
async def file_changed_hook(
        filename: str = Form(...),
        event_type: str = Form(...),
        file: UploadFile = File(...)
) -> None:
    logging.info(f"Received file change event: {filename} {event_type}")
    collection = _get_or_create_chroma_collection()
    client = _create_ollama_client()

    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1]) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        extracted_data = extract_auto(tmp_path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    for fname, text in extracted_data.items():
        if not text:
            logging.info(f"No text extracted from {fname}")
            continue

        chunker = TextChunker()
        cleaned_text = chunker.clean_text(text)
        #chunks = chunker.chunk_text(cleaned_text)
        chunks = [cleaned_text[i: i + 500] for i in range(0, len(cleaned_text), 500)]
        if chunks:
            max_chunk = max(chunks, key=len)
            print(f"chunks: {len(chunks)}, min_size: {min(len(c) for c in chunks)}, max_size: {len(max_chunk)}, max_element: {max_chunk}")
        else:
            print(f"chunks: 0")

        if not chunks:
            logging.info(f"No chunks extracted from {fname}")
            continue

        response = await client.embed(model="nomic-embed-text", input=chunks)
        embeddings = response.embeddings

        ids = [f"{fname}_{i}" for i in range(len(chunks))]
        metadatas = [{"filename": fname} for _ in range(len(chunks))]

        collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=chunks,
            metadatas=metadatas
        )
        logging.info(f"Successfully indexed {len(chunks)} chunks for {fname}")
