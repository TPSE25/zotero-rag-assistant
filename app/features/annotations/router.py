import asyncio
import logging
import os
import tempfile
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any, Dict, List, Optional, cast

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import StreamingResponse
from ollama import AsyncClient

from core.clients import create_ollama_client
from core.settings import ANSWER_MODEL
from features.annotations.schemas import (
    AnnotationDoneEvent,
    AnnotationMatchesEvent,
    AnnotationUpdateProgressEvent,
    ErrorEvent,
    RagPdfMatch,
    RagPopupConfig,
    ndjson_annotation,
)
from features.annotations.service import normalize_rects, parse_page_range
from features.annotations.llm_service import process_annotations as process_annotations_llm

router = APIRouter(tags=["annotations"])

AnnotationProgressCb = Callable[[Dict[str, Any]], Awaitable[None]]
AnnotationMatchesCb = Callable[[List[Dict[str, Any]]], Awaitable[None]]


@router.post("/api/annotations", response_model=None)
async def annotations(
    file: UploadFile = File(...),
    config: str = Form(...),
    ollama_client: AsyncClient = Depends(create_ollama_client),
) -> StreamingResponse:
    cfg = RagPopupConfig.model_validate_json(config)
    page_range = parse_page_range(cfg.pageRange)

    def _to_rag_match(m: Dict[str, Any]) -> RagPdfMatch:
        return RagPdfMatch(
            id=cast(str, m["id"]),
            pageIndex=cast(int, m["page"]),
            rects=normalize_rects(cast(list[tuple[float, float, float, float] | None], m["rects"])),
            text=cast(str | None, m.get("text")),
        )

    async def _compute(
        pdf_path: str,
        progress_cb: AnnotationProgressCb,
        matches_cb: AnnotationMatchesCb,
    ) -> None:
        llm_debug: List[Dict[str, Any]] = []
        await progress_cb({"stage": "file_uploaded"})
        await process_annotations_llm(
            pdf_path=pdf_path,
            rules=cfg.rules,
            answer_model=ANSWER_MODEL,
            ollama_client=ollama_client,
            chunk_size=cfg.chunkLength,
            debug_events=llm_debug,
            page_range=page_range,
            progress_callback=progress_cb,
            chunk_matches_callback=matches_cb,
        )

    if not cfg.rules:

        async def empty_gen() -> AsyncIterator[str]:
            yield ndjson_annotation(AnnotationUpdateProgressEvent(stage="done", completed=0, total=0))
            yield ndjson_annotation(AnnotationDoneEvent())

        return StreamingResponse(
            empty_gen(),
            media_type="application/x-ndjson",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            while content := await file.read(1024 * 1024):
                tmp.write(content)
            tmp_path = tmp.name
    except Exception as e:
        logging.error(f"Failed to persist uploaded PDF: {e}")

        async def error_gen() -> AsyncIterator[str]:
            yield ndjson_annotation(ErrorEvent(message=f"Failed to read uploaded PDF: {e}"))
            yield ndjson_annotation(AnnotationDoneEvent())

        return StreamingResponse(
            error_gen(),
            media_type="application/x-ndjson",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    async def gen() -> AsyncIterator[str]:
        queue: asyncio.Queue[str | None] = asyncio.Queue()

        async def progress_cb(payload: Dict[str, Any]) -> None:
            yield_event = AnnotationUpdateProgressEvent(
                stage=cast(str, payload.get("stage", "annotation_progress")),
                debug=cast(Optional[str], payload.get("debug")),
                sent=cast(Optional[int], payload.get("dispatched_chunks")),
                chunk=cast(Optional[int], payload.get("chunk_number")),
                marker=cast(Optional[int], payload.get("marker_index")),
                markerTotal=cast(Optional[int], payload.get("marker_total")),
                markerId=cast(Optional[str], payload.get("marker_id")),
                completed=cast(Optional[int], payload.get("completed_chunks")),
                total=cast(Optional[int], payload.get("total_chunks")),
            )
            await queue.put(ndjson_annotation(yield_event))

        async def matches_cb(partial: List[Dict[str, Any]]) -> None:
            event = AnnotationMatchesEvent(matches=[_to_rag_match(m).model_dump() for m in partial])
            await queue.put(ndjson_annotation(event))

        async def worker() -> None:
            try:
                if tmp_path is None:
                    raise RuntimeError("Temporary PDF path is missing")
                await _compute(pdf_path=tmp_path, progress_cb=progress_cb, matches_cb=matches_cb)
            except Exception as e:
                logging.error(f"Error in annotations stream: {e}")
                await queue.put(ndjson_annotation(ErrorEvent(message=str(e))))
            finally:
                if tmp_path and os.path.exists(tmp_path):
                    os.remove(tmp_path)
                await queue.put(ndjson_annotation(AnnotationDoneEvent()))
                await queue.put(None)

        task = asyncio.create_task(worker())
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                yield item
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(
        gen(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
