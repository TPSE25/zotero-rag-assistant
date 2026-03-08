import logging
import os
import tempfile
from collections.abc import Sequence
from typing import cast

from fastapi import APIRouter, File, Form, UploadFile

from core.clients import create_ollama_client, get_or_create_chroma_collection
from core.settings import EMBEDDING_MODEL
from core.types import ChromaMetadata, Embedding
from services.document.file_extractor import extract_auto
from services.document.text_chunking import TextChunker

router = APIRouter(tags=["ingest"])


def _document_id(zotero_id: str, filename: str, idx: int) -> str:
    return f"{zotero_id}_{filename}_{idx}"


@router.post("/internal/file-changed")
async def file_changed_hook(
    filename: str = Form(...),
    event_type: str = Form(...),
    file: UploadFile = File(...),
) -> None:
    logging.info(f"Received file change event: {filename} {event_type}")
    collection = get_or_create_chroma_collection()
    client = create_ollama_client()

    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1]) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        extracted_data = extract_auto(tmp_path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    zotero_id, extension = os.path.splitext(os.path.basename(filename))
    if extension != ".prop":
        collection.delete(where={"zotero_id": zotero_id})

    for fname, text in extracted_data.items():
        if not text:
            logging.info(f"No text extracted from {fname}")
            continue

        chunker = TextChunker()
        cleaned_text = chunker.clean_text(text)
        chunks = chunker.chunk_text(cleaned_text)

        if not chunks:
            logging.info(f"No chunks extracted from {fname}")
            continue

        response = await client.embed(model=EMBEDDING_MODEL, input=chunks)
        embeddings: list[Embedding] = [cast(Sequence[float], e) for e in response.embeddings]

        ids = [_document_id(zotero_id, fname, i) for i in range(len(chunks))]
        metadatas: list[ChromaMetadata] = [
            {"filename": fname, "zotero_id": zotero_id, "chunk_index": i}
            for i in range(len(chunks))
        ]

        collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=chunks,
            metadatas=metadatas,
        )
        logging.info(f"Successfully indexed {len(chunks)} chunks for {fname}")
