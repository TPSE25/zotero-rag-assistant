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

# Concurrency limits
MAX_CONCURRENT_LLM_CALLS = 2
MAX_CONCURRENT_CHUNKS = 2
MAX_CONCURRENT_REFINEMENTS = 2

OLLAMA_SEMAPHORE = asyncio.Semaphore(MAX_CONCURRENT_LLM_CALLS)
CHUNK_SEMAPHORE = asyncio.Semaphore(MAX_CONCURRENT_CHUNKS)
REFINE_SEMAPHORE = asyncio.Semaphore(MAX_CONCURRENT_REFINEMENTS)

# ===============================
# DATA CLASSES
# ===============================
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

class RuleLike(Protocol):
    id: str
    termsRaw: str

def _is_regex_rule(rule: RuleLike) -> bool:
    terms = rule.termsRaw.strip()
    if terms.startswith("REGEX:"):
        return True
    if re.fullmatch(r"([A-Z]{2,5}|([A-Z]\.){2,5})", terms):
        return True
    return False

def _process_regex_rules(tokens: List[Token], rules: Sequence[RuleLike]) -> List[ExactSpanMatch]:
    matches: List[ExactSpanMatch] = []

    for rule in rules:
        terms = rule.termsRaw.strip()
        pattern_text = terms[6:] if terms.startswith("REGEX:") else terms

        try:
            pattern = re.compile(pattern_text)
        except re.error:
            logger.warning("Invalid regex for rule %s", rule.id)
            continue

        for idx, token in enumerate(tokens):
            if token.text and pattern.fullmatch(token.text):
                matches.append(
                    ExactSpanMatch(rule_id=rule.id, start_token=idx, end_token=idx)
                )

    return matches

# ===============================
# HEURISTIC RULES
# ===============================
def _process_heuristic_rules(tokens: List[Token], rules: Sequence[RuleLike]) -> List[ExactSpanMatch]:
    matches: List[ExactSpanMatch] = []

    for rule in rules:
        for idx, t in enumerate(tokens):
            text = t.text.strip()

            # Links / DOIs / www
            if "link" in rule.termsRaw.lower():
                if re.search(r"(https?://|www\.|doi:)", text, re.IGNORECASE):
                    matches.append(ExactSpanMatch(rule_id=rule.id, start_token=idx, end_token=idx))

            # Abbreviations (U.S., NATO, NASA, etc.)
            elif "abbreviation" in rule.termsRaw.lower():
                if re.fullmatch(r"([A-Z]{2,5}|([A-Z]\.){1,5})", text):
                    matches.append(ExactSpanMatch(rule_id=rule.id, start_token=idx, end_token=idx))

    return matches

async def process_annotations(
    pdf_path: str,
    rules: Sequence[RuleLike],
    answer_model: str,
    ollama_client: AsyncClient,
    debug_events: Optional[List[dict[str, Any]]] = None,
) -> List[dict[str, Any]]:

    recognizer = TextPlaceRecognitionPDF(pdf_path)
    pages = recognizer.extract_text()
    if not pages:
        return []

    # Flatten all tokens
    all_tokens: List[Token] = [
        Token(text=w["text"], rect=w["rect"], page=p["page"])
        for p in pages for w in p["words"]
    ]
    if not all_tokens:
        return []

    # Split rules
    regex_rules = [r for r in rules if _is_regex_rule(r)]
    semantic_rules = [r for r in rules if not _is_regex_rule(r)]

    # 1️⃣ Apply regex rules
    regex_hits = _process_regex_rules(all_tokens, regex_rules)

    # 2️⃣ Apply heuristic rules
    heuristic_hits = _process_heuristic_rules(all_tokens, semantic_rules)

    all_hits: List[ExactSpanMatch] = regex_hits + heuristic_hits

    # 3️⃣ If nothing found and semantic rules exist, fallback to LLM
    if semantic_rules and not heuristic_hits:
        chunks = _create_chunks(all_tokens, chunk_size=1000, overlap=150)

        async def _guarded_chunk(chunk):
            async with CHUNK_SEMAPHORE:
                return await _process_chunk(
                    chunk, semantic_rules, answer_model, ollama_client, debug_events
                )

        tasks = [_guarded_chunk(chunk) for chunk in chunks]
        chunk_results = await asyncio.gather(*tasks)

        for chunk, results in zip(chunks, chunk_results):
            for hit in results:
                all_hits.append(
                    ExactSpanMatch(
                        rule_id=hit.rule_id,
                        start_token=chunk.start_index + hit.start_token,
                        end_token=chunk.start_index + hit.end_token,
                    )
                )

    # 4️⃣ Build final output with page + rects
    seen_spans: set[tuple[str, int, int]] = set()
    final_matches: List[dict[str, Any]] = []

    for hit in all_hits:
        key = (hit.rule_id, hit.start_token, hit.end_token)
        if key in seen_spans:
            continue
        seen_spans.add(key)

        by_page: dict[int, list[Rect]] = {}
        for idx in range(hit.start_token, hit.end_token + 1):
            tok = all_tokens[idx]
            if tok.rect:
                by_page.setdefault(tok.page, []).append(tok.rect)

        for page_idx, rects in by_page.items():
            final_matches.append({"id": hit.rule_id, "page": page_idx, "rects": rects})

    return final_matches


def _create_chunks(tokens: List[Token], chunk_size: int, overlap: int) -> List[Chunk]:
    chunks: List[Chunk] = []
    if len(tokens) <= chunk_size:
        return [Chunk(text=" ".join(t.text for t in tokens), tokens=tokens, sentences=_create_sentences(tokens), start_index=0)]

    step = chunk_size - overlap
    for i in range(0, len(tokens), max(1, step)):
        batch = tokens[i:i+chunk_size]
        if not batch:
            break
        chunks.append(Chunk(text=" ".join(t.text for t in batch), tokens=batch, sentences=_create_sentences(batch), start_index=i))
        if len(batch) < overlap and i > 0:
            break
    return chunks

def _create_sentences(tokens: List[Token], max_tokens_per_sentence: int = 80) -> List[SentenceSpan]:
    sentences: List[SentenceSpan] = []
    if not tokens:
        return sentences
    start, sid_counter = 0, 1
    def _ends_sentence(t: str) -> bool:
        return bool(re.search(r"[.!?][\"'”’)\]]*$", t))
    for i in range(len(tokens)):
        if _ends_sentence(tokens[i].text) or (i - start + 1 >= max_tokens_per_sentence):
            sent_tokens = tokens[start:i+1]
            sentences.append(SentenceSpan(sid=f"S{sid_counter}", text=" ".join(t.text for t in sent_tokens), token_start=start, token_end=i))
            sid_counter += 1
            start = i + 1
    if start < len(tokens):
        sentences.append(SentenceSpan(sid=f"S{sid_counter}", text=" ".join(t.text for t in tokens[start:]), token_start=start, token_end=len(tokens)-1))
    return sentences


async def _process_chunk(chunk, rules, model, client, debug_events):
    if not chunk.sentences:
        return []

    try:
        coarse_hits = await _llm_find_relevant_sentences(chunk, rules, model, client, debug_events)
    except Exception as e:
        logger.error("Coarse selection failed: %s", e)
        return []

    rule_map = {r.id: r for r in rules}
    sentence_by_id = {s.sid: s for s in chunk.sentences}
    sentence_pos = {s.sid: idx for idx, s in enumerate(chunk.sentences)}

    refinement_tasks = []

    for hit in coarse_hits:
        if hit.rule_id not in rule_map:
            continue
        valid_ids = sorted({sid for sid in hit.sentence_ids if sid in sentence_by_id}, key=lambda x: sentence_pos[x])
        if not valid_ids:
            continue
        groups = _group_contiguous_sentence_ids(valid_ids, sentence_pos)
        for group_ids in groups:
            group_sentences = [sentence_by_id[sid] for sid in group_ids]
            local_start = group_sentences[0].token_start
            local_end = group_sentences[-1].token_end

            async def _guarded_refine(rule_id, tokens_slice, local_start):
                async with REFINE_SEMAPHORE:
                    result = await _llm_refine_span_boundaries(rule_map[rule_id], tokens_slice, model, client, debug_events)
                    return result, local_start, rule_id

            refinement_tasks.append(_guarded_refine(hit.rule_id, chunk.tokens[local_start:local_end+1], local_start))

    results = await asyncio.gather(*refinement_tasks)
    exact_matches: List[ExactSpanMatch] = []

    for boundaries, local_start, rule_id in results:
        if not boundaries:
            continue
        for b in boundaries:
            exact_matches.append(ExactSpanMatch(rule_id=rule_id, start_token=local_start+b.start_token, end_token=local_start+b.end_token))

    return exact_matches

def _group_contiguous_sentence_ids(sentence_ids, sentence_pos):
    if not sentence_ids:
        return []
    ordered = sorted(sentence_ids, key=lambda sid: sentence_pos[sid])
    groups, current = [], [ordered[0]]
    for sid in ordered[1:]:
        if sentence_pos[sid] == sentence_pos[current[-1]] + 1:
            current.append(sid)
        else:
            groups.append(current)
            current = [sid]
    groups.append(current)
    return groups

def _parse_json_from_llm(raw: str):
    raw = raw.strip()
    try:
        return json.loads(raw)
    except:
        pass
    raw_no_fence = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.IGNORECASE | re.DOTALL).strip()
    try:
        return json.loads(raw_no_fence)
    except:
        pass
    match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    if match:
        return json.loads(match.group(0))
    raise ValueError(f"Could not parse JSON: {raw[:200]}")