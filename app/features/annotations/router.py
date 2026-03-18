import asyncio
import contextlib
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
    AnnotationConcurrencyEvent,
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


class _AnnotationConcurrencyTracker:
    def __init__(self) -> None:
        self._active_requests = 0
        self._subscribers: set[asyncio.Queue[int]] = set()
        self._lock = asyncio.Lock()

    async def subscribe(self) -> asyncio.Queue[int]:
        queue: asyncio.Queue[int] = asyncio.Queue()
        async with self._lock:
            self._subscribers.add(queue)
            current = self._active_requests
        await queue.put(current)
        return queue

    async def unsubscribe(self, queue: asyncio.Queue[int]) -> None:
        async with self._lock:
            self._subscribers.discard(queue)

    async def increment(self) -> None:
        await self._change_active_requests(1)

    async def decrement(self) -> None:
        await self._change_active_requests(-1)

    async def _change_active_requests(self, delta: int) -> None:
        async with self._lock:
            self._active_requests = max(0, self._active_requests + delta)
            current = self._active_requests
            subscribers = list(self._subscribers)

        for subscriber in subscribers:
            await subscriber.put(current)


ANNOTATION_CONCURRENCY_TRACKER = _AnnotationConcurrencyTracker()


@router.post("/api/annotations", response_model=None)
async def annotations(
    file: UploadFile = File(...),
    config: str = Form(...),
    ollama_client: AsyncClient = Depends(create_ollama_client),
) -> StreamingResponse:
    # Parse and validate configuration JSON into a typed config object
    cfg = RagPopupConfig.model_validate_json(config)

    # Parse page range (e.g., "1-5") into usable format
    page_range = parse_page_range(cfg.pageRange)

    # Helper: convert raw match dict into strongly typed RagPdfMatch
    def _to_rag_match(m: Dict[str, Any]) -> RagPdfMatch:
        return RagPdfMatch(
            id=cast(str, m["id"]),
            pageIndex=cast(int, m["page"]),
            rects=normalize_rects(
                cast(list[tuple[float, float, float, float] | None], m["rects"])
            ),
            text=cast(str | None, m.get("text")),
        )

    # Core computation function: runs LLM-based annotation pipeline
    async def _compute(
        pdf_path: str,
        progress_cb: AnnotationProgressCb,
        matches_cb: AnnotationMatchesCb,
    ) -> None:
        llm_debug: List[Dict[str, Any]] = []

        # Notify that file upload stage is complete
        await progress_cb({"stage": "file_uploaded"})

        # Run annotation pipeline using LLM
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

    # If no rules provided → return immediately with "done"
    if not cfg.rules:

        async def empty_gen() -> AsyncIterator[str]:
            yield ndjson_annotation(
                AnnotationUpdateProgressEvent(stage="done", completed=0, total=0)
            )
            yield ndjson_annotation(AnnotationDoneEvent())

        return StreamingResponse(
            empty_gen(),
            media_type="application/x-ndjson",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    # Save uploaded PDF to a temporary file
    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            # Stream file in chunks to avoid large memory usage
            while content := await file.read(1024 * 1024):
                tmp.write(content)
            tmp_path = tmp.name
    except Exception as e:
        logging.error(f"Failed to persist uploaded PDF: {e}")
        error_message = f"Failed to read uploaded PDF: {e}"

        # Return error as streaming response
        async def error_gen() -> AsyncIterator[str]:
            yield ndjson_annotation(ErrorEvent(message=error_message))
            yield ndjson_annotation(AnnotationDoneEvent())

        return StreamingResponse(
            error_gen(),
            media_type="application/x-ndjson",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    # Main streaming generator
    async def gen() -> AsyncIterator[str]:
        # Queue used to communicate events between workers and stream
        queue: asyncio.Queue[str | None] = asyncio.Queue()

        # Subscribe to concurrency tracker (for monitoring active requests)
        concurrency_queue = await ANNOTATION_CONCURRENCY_TRACKER.subscribe()

        # Callback: sends progress updates into stream
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

        # Callback: sends partial annotation matches
        async def matches_cb(partial: List[Dict[str, Any]]) -> None:
            event = AnnotationMatchesEvent(
                matches=[_to_rag_match(m).model_dump() for m in partial]
            )
            await queue.put(ndjson_annotation(event))

        # Worker: streams concurrency updates continuously
        async def concurrency_worker() -> None:
            while True:
                active_requests = await concurrency_queue.get()
                event = AnnotationConcurrencyEvent(activeRequests=active_requests)
                await queue.put(ndjson_annotation(event))

        # Main worker: runs annotation pipeline
        async def worker() -> None:
            is_counted = False
            try:
                # Increment active request counter
                await ANNOTATION_CONCURRENCY_TRACKER.increment()
                is_counted = True

                if tmp_path is None:
                    raise RuntimeError("Temporary PDF path is missing")

                # Run annotation computation
                await _compute(
                    pdf_path=tmp_path,
                    progress_cb=progress_cb,
                    matches_cb=matches_cb,
                )

            except Exception as e:
                logging.error(f"Error in annotations stream: {e}")
                # Send error event to stream
                await queue.put(ndjson_annotation(ErrorEvent(message=str(e))))

            finally:
                # Decrement concurrency counter
                if is_counted:
                    await ANNOTATION_CONCURRENCY_TRACKER.decrement()

                # Clean up temporary file
                if tmp_path and os.path.exists(tmp_path):
                    os.remove(tmp_path)

                # Signal completion
                await queue.put(ndjson_annotation(AnnotationDoneEvent()))
                await queue.put(None)  # Sentinel to stop generator

        # Start background tasks
        concurrency_task = asyncio.create_task(concurrency_worker())
        task = asyncio.create_task(worker())

        try:
            # Continuously stream events from queue
            while True:
                item = await queue.get()
                if item is None:
                    break
                yield item
        finally:
            # Cleanup tasks on exit
            if not task.done():
                task.cancel()
            if not concurrency_task.done():
                concurrency_task.cancel()

            # Unsubscribe from concurrency tracker
            await ANNOTATION_CONCURRENCY_TRACKER.unsubscribe(concurrency_queue)

            # Suppress cancellation errors
            with contextlib.suppress(asyncio.CancelledError):
                await concurrency_task

    # Return streaming NDJSON response
    return StreamingResponse(
        gen(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )