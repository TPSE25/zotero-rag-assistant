from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any, List, Optional, Protocol

from ollama import AsyncClient
from pydantic import BaseModel, Field

from features.annotations.pdf_text_recognition import Rect, TextPlaceRecognitionPDF
from features.prompts.store import render_prompt

# Logger for debugging and error reporting
logger = logging.getLogger(__name__)

# Maximum number of concurrent LLM calls
MAX_OLLAMA_PARALLEL_CALLS = 4


# Protocol defining the structure of a rule
class RuleLike(Protocol):
    id: str
    termsRaw: str


# Represents a single token (word) in the document
@dataclass
class Token:
    text: str
    rect: Optional[Rect]  # Bounding box
    page: int             # Page index


# Represents a sentence span within tokens
@dataclass
class SentenceSpan:
    sid: str              # Sentence ID (e.g., S1, S2)
    text: str             # Sentence text
    token_start: int      # Start index in token list
    token_end: int        # End index in token list


# Represents a chunk of tokens processed together
@dataclass
class Chunk:
    text: str
    tokens: List[Token]
    sentences: List[SentenceSpan]
    start_index: int      # Offset in global token list


# Represents an exact match span
@dataclass
class ExactSpanMatch:
    rule_id: str
    start_token: int
    end_token: int


# LLM response: coarse matching (sentence-level)
class CoarseMatchResult(BaseModel):
    rule_id: str
    sentence_ids: List[str] = Field(default_factory=list)


class LLMCoarseResponse(BaseModel):
    matches: List[CoarseMatchResult] = Field(default_factory=list)


# LLM response: fine-grained boundary refinement
class LLMBoundarySpan(BaseModel):
    start_token: int
    end_token: int


class LLMBoundaryResponse(BaseModel):
    spans: List[LLMBoundarySpan] = Field(default_factory=list)


# Callback types for progress and partial results
ProgressCallback = Callable[[dict[str, Any]], Awaitable[None]]
ChunkMatchesCallback = Callable[[List[dict[str, Any]]], Awaitable[None]]


async def process_annotations(
    pdf_path: str,
    rules: Sequence[RuleLike],
    answer_model: str,
    ollama_client: AsyncClient,
    chunk_size: Optional[int] = None,
    debug_events: Optional[List[dict[str, Any]]] = None,
    page_range: Optional[tuple[int, int]] = None,
    progress_callback: Optional[ProgressCallback] = None,
    chunk_matches_callback: Optional[ChunkMatchesCallback] = None,
) -> List[dict[str, Any]]:

    # Extract text + positions from PDF
    recognizer = TextPlaceRecognitionPDF(pdf_path)
    pages = recognizer.extract_text()

    # Filter by page range if provided
    if page_range is not None:
        start_page, end_page = page_range
        pages = [p for p in pages if start_page <= p["page"] <= end_page]

    if not pages:
        return []

    # Notify progress
    if progress_callback is not None:
        await progress_callback({"stage": "text_extracted", "pages": len(pages)})

    # Flatten words into tokens
    all_tokens: List[Token] = []
    for page in pages:
        for word in page["words"]:
            all_tokens.append(Token(
                text=word["text"],
                rect=word["rect"],
                page=page["page"]
            ))

    if not all_tokens:
        return []

    if progress_callback is not None:
        await progress_callback({"stage": "tokens_indexed", "tokens": len(all_tokens)})

    # Split tokens into overlapping chunks
    resolved_chunk_size = chunk_size or 1600
    chunks = _create_chunks(all_tokens, chunk_size=resolved_chunk_size, overlap=150)

    if progress_callback is not None:
        await progress_callback({"stage": "chunking_done", "total_chunks": len(chunks)})

    # Deduplication set for spans
    seen_spans: set[tuple[str, int, int]] = set()
    final_matches: List[dict[str, Any]] = []

    # Limit concurrent LLM calls
    ollama_chat_semaphore = asyncio.Semaphore(MAX_OLLAMA_PARALLEL_CALLS)

    # Process a single chunk
    async def _run_chunk(chunk: Chunk, chunk_number: int, total_chunks: int):
        if progress_callback is not None:
            await progress_callback({
                "stage": "chunk_started",
                "chunk_number": chunk_number,
                "total_chunks": total_chunks,
            })

        return chunk_number, chunk, await _process_chunk(
            chunk,
            rules,
            answer_model,
            ollama_client,
            ollama_chat_semaphore,
            debug_events,
            progress_callback=progress_callback,
            chunk_number=chunk_number,
            total_chunks=total_chunks,
        )

    # Dispatch all chunks asynchronously
    tasks = []
    dispatched_chunks = 0

    for i, chunk in enumerate(chunks, start=1):
        tasks.append(asyncio.create_task(_run_chunk(chunk, i, len(chunks))))
        dispatched_chunks += 1

        if progress_callback is not None:
            await progress_callback({
                "stage": "chunk_dispatched",
                "dispatched_chunks": dispatched_chunks,
                "total_chunks": len(chunks),
            })

    # Collect results as they complete
    completed_chunks = 0

    for task in asyncio.as_completed(tasks):
        _, chunk, results = await task
        chunk_matches: List[dict[str, Any]] = []

        for hit in results:
            # Convert local token indices to global indices
            global_start = chunk.start_index + hit.start_token
            global_end = chunk.start_index + hit.end_token
            key = (hit.rule_id, global_start, global_end)

            # Skip duplicates
            if key in seen_spans:
                continue
            seen_spans.add(key)

            # Group bounding boxes by page
            by_page: dict[int, list[Rect]] = {}
            for idx in range(hit.start_token, hit.end_token + 1):
                tok = chunk.tokens[idx]
                if tok.rect:
                    by_page.setdefault(tok.page, []).append(tok.rect)

            # Build final match objects
            for page_idx, rects in by_page.items():
                page_tokens = [
                    chunk.tokens[idx].text
                    for idx in range(hit.start_token, hit.end_token + 1)
                    if chunk.tokens[idx].page == page_idx
                ]

                chunk_matches.append({
                    "id": hit.rule_id,
                    "page": page_idx,
                    "rects": rects,
                    "text": " ".join(page_tokens).strip()
                })

        # Emit partial results
        if chunk_matches:
            final_matches.extend(chunk_matches)
            if chunk_matches_callback is not None:
                await chunk_matches_callback(chunk_matches)

        completed_chunks += 1

        if progress_callback is not None:
            await progress_callback({
                "stage": "chunk_processed",
                "completed_chunks": completed_chunks,
                "total_chunks": len(chunks),
                "matches_so_far": len(final_matches),
            })

    if progress_callback is not None:
        await progress_callback({"stage": "done", "matches": len(final_matches)})

    return final_matches


# Splits tokens into overlapping chunks
def _create_chunks(tokens: List[Token], chunk_size: int, overlap: int) -> List[Chunk]:
    chunks: List[Chunk] = []

    # If small enough → single chunk
    if len(tokens) <= chunk_size:
        batch = tokens
        return [Chunk(
            text=" ".join(t.text for t in batch),
            tokens=batch,
            sentences=_create_sentences(batch),
            start_index=0
        )]

    step = max(1, chunk_size - overlap)

    # Sliding window over tokens
    for i in range(0, len(tokens), step):
        batch = tokens[i:i + chunk_size]
        if not batch:
            break

        chunks.append(Chunk(
            text=" ".join(t.text for t in batch),
            tokens=batch,
            sentences=_create_sentences(batch),
            start_index=i
        ))

        # Stop if remaining tokens are too small
        if len(batch) < overlap and i > 0:
            break

    return chunks


# Splits tokens into sentences
def _create_sentences(tokens: List[Token], max_tokens_per_sentence: int = 80) -> List[SentenceSpan]:
    sentences: List[SentenceSpan] = []
    if not tokens:
        return sentences

    start = 0
    sid_counter = 1

    # Heuristic: detect sentence endings via punctuation
    def _ends_sentence(tok_text: str) -> bool:
        return bool(re.search(r"[.!?][\"'”’)\]]*$", tok_text)) or bool(re.search(r"[.!?]$", tok_text))

    i = 0
    while i < len(tokens):
        current_len = i - start + 1
        is_boundary = _ends_sentence(tokens[i].text)

        # Force split if too long
        if not is_boundary and current_len >= max_tokens_per_sentence:
            is_boundary = True

        if is_boundary:
            sentences.append(SentenceSpan(
                sid=f"S{sid_counter}",
                text=" ".join(t.text for t in tokens[start:i + 1]),
                token_start=start,
                token_end=i
            ))
            sid_counter += 1
            start = i + 1

        i += 1

    # Handle trailing tokens
    if start < len(tokens):
        sentences.append(SentenceSpan(
            sid=f"S{sid_counter}",
            text=" ".join(t.text for t in tokens[start:]),
            token_start=start,
            token_end=len(tokens) - 1
        ))

    return sentences


# Groups consecutive sentence IDs into contiguous blocks
def _group_contiguous_sentence_ids(sentence_ids: List[str], sentence_pos: dict[str, int]) -> List[List[str]]:
    if not sentence_ids:
        return []

    ordered = sorted(sentence_ids, key=lambda sid: sentence_pos[sid])
    groups = []
    current_group = [ordered[0]]

    for sid in ordered[1:]:
        prev_sid = current_group[-1]
        if sentence_pos[sid] == sentence_pos[prev_sid] + 1:
            current_group.append(sid)
        else:
            groups.append(current_group)
            current_group = [sid]

    groups.append(current_group)
    return groups


# Robust JSON parsing from LLM output
def _parse_json_from_llm(raw: str) -> Any:
    raw = raw.strip()

    # Try direct parse
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Remove markdown fences (```json ... ```)
    raw_no_fence = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.IGNORECASE | re.DOTALL).strip()
    try:
        return json.loads(raw_no_fence)
    except json.JSONDecodeError:
        pass

    # Extract JSON substring
    match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    if match:
        return json.loads(match.group(0))

    raise ValueError(f"Could not parse JSON from LLM response: {raw[:500]}")