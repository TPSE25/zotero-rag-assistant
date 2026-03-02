from __future__ import annotations
import asyncio
import json
import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, List, Optional, Protocol

from ollama import AsyncClient
from pydantic import BaseModel, Field
from prompt_store import render_prompt
from text_place_recognition_pdf import TextPlaceRecognitionPDF, Rect

logger = logging.getLogger(__name__)

# --- Protocols & Data Classes ---

class RuleLike(Protocol):
    id: str
    termsRaw: str

@dataclass
class Token:
    text: str
    rect: Optional[Rect]
    page: int

@dataclass
class SentenceSpan:
    sid: str
    text: str
    token_start: int
    token_end: int

@dataclass
class Chunk:
    text: str
    tokens: List[Token]
    sentences: List[SentenceSpan]
    start_index: int

@dataclass
class ExactSpanMatch:
    rule_id: str
    start_token: int
    end_token: int

# --- Pydantic Schemas for LLM JSON Response ---

class CoarseMatchResult(BaseModel):
    rule_id: str
    sentence_ids: List[str] = Field(default_factory=list)

class LLMCoarseResponse(BaseModel):
    matches: List[CoarseMatchResult] = Field(default_factory=list)

class LLMBoundarySpan(BaseModel):
    start_token: int
    end_token: int

class LLMBoundaryResponse(BaseModel):
    spans: List[LLMBoundarySpan] = Field(default_factory=list)

# --- Main Logic ---

async def process_annotations(
    pdf_path: str,
    rules: Sequence[RuleLike],
    answer_model: str,
    ollama_client: AsyncClient,
    debug_events: Optional[List[dict[str, Any]]] = None,
) -> dict[str, Any]:
    """
    Orchestrates the annotation process and returns a dict with 'matches' and 'llmDebug'.
    """
    if debug_events is None:
        debug_events = []

    recognizer = TextPlaceRecognitionPDF(pdf_path)
    pages = recognizer.extract_text()
    if not pages:
        return {"matches": [], "llmDebug": debug_events}

    all_tokens = [
        Token(text=w["text"], rect=w["rect"], page=p["page"])
        for p in pages for w in p["words"]
    ]
    
    if not all_tokens:
        return {"matches": [], "llmDebug": debug_events}

    # 1. Chunking
    chunks = _create_chunks(all_tokens, chunk_size=1200, overlap=150)
    
    # 2. Parallel Processing
    tasks = [
        _process_chunk(chunk, rules, answer_model, ollama_client, debug_events) 
        for chunk in chunks
    ]
    chunk_results = await asyncio.gather(*tasks)

    # 3. Aggregation & Coordinate Mapping
    seen_spans: set[tuple[str, int, int]] = set()
    final_matches: List[dict[str, Any]] = []

    for chunk, results in zip(chunks, chunk_results):
        for hit in results:
            g_start = chunk.start_index + hit.start_token
            g_end = chunk.start_index + hit.end_token
            key = (hit.rule_id, g_start, g_end)
            
            if key in seen_spans:
                continue
            seen_spans.add(key)

            by_page: dict[int, list[Rect]] = {}
            for idx in range(hit.start_token, hit.end_token + 1):
                t = chunk.tokens[idx]
                if t.rect:
                    by_page.setdefault(t.page, []).append(t.rect)

            for p_idx, rects in by_page.items():
                final_matches.append({"id": hit.rule_id, "page": p_idx, "rects": rects})

    return {
        "matches": final_matches,
        "llmDebug": debug_events
    }

async def _process_chunk(chunk, rules, model, client, debug) -> List[ExactSpanMatch]:
    if not chunk.sentences:
        return []

    try:
        coarse_hits = await _llm_find_relevant_sentences(chunk, rules, model, client, debug)
    except Exception as e:
        logger.error(f"Coarse fail: {e}")
        return []

    sentence_by_id = {s.sid: s for s in chunk.sentences}
    sentence_pos = {s.sid: idx for idx, s in enumerate(chunk.sentences)}
    rule_map = {r.id: r for r in rules}
    exact_matches = []

    for hit in coarse_hits:
        if hit.rule_id not in rule_map:
            continue
        
        valid_ids = sorted([sid for sid in hit.sentence_ids if sid in sentence_by_id], 
                           key=lambda x: sentence_pos[x])
        if not valid_ids:
            continue

        groups = _group_contiguous_sentence_ids(valid_ids, sentence_pos)
        for g_ids in groups:
            g_sents = [sentence_by_id[sid] for sid in g_ids]
            l_start, l_end = g_sents[0].token_start, g_sents[-1].token_end
            
            boundaries = await _llm_refine_span_boundaries(
                rule_map[hit.rule_id], chunk.tokens[l_start:l_end+1], 
                model, client, chunk.start_index, debug
            )

            if boundaries:
                for b in boundaries:
                    exact_matches.append(ExactSpanMatch(
                        hit.rule_id, l_start + b.start_token, l_start + b.end_token
                    ))
    return exact_matches

# --- LLM Helper Functions ---

async def _llm_find_relevant_sentences(chunk, rules, model, client, debug):
    rule_desc = "\n".join([f'- ID "{r.id}": {r.termsRaw}' for r in rules])
    sent_block = "\n".join([f"[{s.sid}] {s.text}" for s in chunk.sentences])
    prompt = render_prompt("annotation_coarse_user", {"rule_descriptions": rule_desc, "sentence_block": sent_block})

    response = await client.chat(model=model, messages=[{"role": "user", "content": prompt}], 
                                 format=LLMCoarseResponse.model_json_schema(), options={"temperature": 0.0})
    
    raw = response["message"]["content"]
    if debug is not None:
        debug.append({"stage": "coarse", "chunk": chunk.start_index, "response": raw})
    
    data = LLMCoarseResponse.model_validate(_parse_json(raw))
    return data.matches

async def _llm_refine_span_boundaries(rule, tokens, model, client, chunk_idx, debug):
    token_lines = "\n".join(f"[{i}] {t.text}" for i, t in enumerate(tokens))
    prompt = render_prompt("annotation_boundary_user", {
        "rule_id": rule.id, "rule_terms": rule.termsRaw, 
        "plain_text": " ".join(t.text for t in tokens), "token_lines": token_lines
    })

    response = await client.chat(model=model, messages=[{"role": "user", "content": prompt}], 
                                 format=LLMBoundaryResponse.model_json_schema(), options={"temperature": 0.0})
    
    raw = response["message"]["content"]
    if debug is not None:
        debug.append({"stage": "refine", "rule_id": rule.id, "response": raw})
        
    data = LLMBoundaryResponse.model_validate(_parse_json(raw))
    return data.spans

# --- Utilities ---

def _create_chunks(tokens, chunk_size, overlap):
    chunks = []
    step = max(1, chunk_size - overlap)
    for i in range(0, len(tokens), step):
        batch = tokens[i : i + chunk_size]
        if not batch: break
        chunks.append(Chunk(" ".join(t.text for t in batch), batch, _create_sentences(batch), i))
        if len(batch) < overlap: break
    return chunks

def _create_sentences(tokens, max_tokens=80):
    sentences, start, sid = [], 0, 1
    for i, t in enumerate(tokens):
        if bool(re.search(r"[.!?][\"'”’\]]*$", t.text)) or (i - start + 1 >= max_tokens):
            sentences.append(SentenceSpan(f"S{sid}", " ".join(tk.text for tk in tokens[start:i+1]), start, i))
            start, sid = i + 1, sid + 1
    if start < len(tokens):
        sentences.append(SentenceSpan(f"S{sid}", " ".join(tk.text for tk in tokens[start:]), start, len(tokens)-1))
    return sentences

def _group_contiguous_sentence_ids(ids, pos):
    if not ids: return []
    ordered = sorted(ids, key=lambda x: pos[x])
    groups, cur = [], [ordered[0]]
    for s in ordered[1:]:
        if pos[s] == pos[cur[-1]] + 1: cur.append(s)
        else: groups.append(cur); cur = [s]
    groups.append(cur)
    return groups

def _parse_json(raw):
    try: return json.loads(raw)
    except:
        match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
        if match: return json.loads(match.group(0))
    return {"matches": [], "spans": []} # Fallback for empty/bad JSON