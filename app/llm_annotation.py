from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from typing import Any, List, Optional, Protocol

from ollama import AsyncClient
from pydantic import BaseModel, Field, ValidationError

from text_place_recognition_pdf import TextPlaceRecognitionPDF, Rect

logger = logging.getLogger(__name__)


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


class CoarseMatchResult(BaseModel):
    rule_id: str
    sentence_ids: List[str] = Field(default_factory=list)


class LLMCoarseResponse(BaseModel):
    matches: List[CoarseMatchResult] = Field(default_factory=list)


class LLMBoundaryResponse(BaseModel):
    start_token: int
    end_token: int



async def process_annotations(
    pdf_path: str,
    rules: List[RuleLike],
    answer_model: str,
    ollama_client: AsyncClient
) -> List[dict[str, Any]]:

    recognizer = TextPlaceRecognitionPDF(pdf_path)
    pages = recognizer.extract_text()

    if not pages:
        return []

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

    chunks = _create_chunks(all_tokens, chunk_size=1600, overlap=150)

    tasks = [
        _process_chunk(chunk, rules, answer_model, ollama_client)
        for chunk in chunks
    ]
    chunk_results = await asyncio.gather(*tasks)

    seen_spans: set[tuple[str, int, int]] = set()
    final_matches: List[dict[str, Any]] = []

    for chunk, results in zip(chunks, chunk_results):
        for hit in results:
            global_start = chunk.start_index + hit.start_token
            global_end = chunk.start_index + hit.end_token
            key = (hit.rule_id, global_start, global_end)

            if key in seen_spans:
                continue
            seen_spans.add(key)

            by_page: dict[int, list[Rect]] = {}

            for idx in range(hit.start_token, hit.end_token + 1):
                tok = chunk.tokens[idx]
                if tok.rect:
                    by_page.setdefault(tok.page, []).append(tok.rect)

            for page_idx, rects in by_page.items():
                final_matches.append({
                    "id": hit.rule_id,
                    "page": page_idx,
                    "rects": rects
                })

    return final_matches

def _create_chunks(tokens: List[Token], chunk_size: int, overlap: int) -> List[Chunk]:
    chunks: List[Chunk] = []

    if len(tokens) <= chunk_size:
        batch = tokens
        text = " ".join(t.text for t in batch)
        sentences = _create_sentences(batch)
        return [Chunk(text=text, tokens=batch, sentences=sentences, start_index=0)]

    step = chunk_size - overlap
    if step < 1:
        step = 1

    for i in range(0, len(tokens), step):
        batch = tokens[i:i + chunk_size]
        if not batch:
            break

        text = " ".join(t.text for t in batch)
        sentences = _create_sentences(batch)
        chunks.append(Chunk(text=text, tokens=batch, sentences=sentences, start_index=i))

        if len(batch) < overlap and i > 0:
            break

    return chunks


def _create_sentences(tokens: List[Token], max_tokens_per_sentence: int = 80) -> List[SentenceSpan]:
    sentences: List[SentenceSpan] = []
    if not tokens:
        return sentences

    start = 0
    sid_counter = 1

    def _ends_sentence(tok_text: str) -> bool:
        return bool(re.search(r"[.!?][\"'”’)\]]*$", tok_text)) or bool(re.search(r"[.!?]$", tok_text))

    i = 0
    while i < len(tokens):
        current_len = i - start + 1
        is_boundary = _ends_sentence(tokens[i].text)

        if not is_boundary and current_len >= max_tokens_per_sentence:
            is_boundary = True

        if is_boundary:
            sent_tokens = tokens[start:i + 1]
            sentences.append(SentenceSpan(
                sid=f"S{sid_counter}",
                text=" ".join(t.text for t in sent_tokens),
                token_start=start,
                token_end=i
            ))
            sid_counter += 1
            start = i + 1

        i += 1

    if start < len(tokens):
        sent_tokens = tokens[start:]
        sentences.append(SentenceSpan(
            sid=f"S{sid_counter}",
            text=" ".join(t.text for t in sent_tokens),
            token_start=start,
            token_end=len(tokens) - 1
        ))

    return sentences


async def _process_chunk(
        chunk: Chunk,
        rules: List[RuleLike],
        model: str,
        client: AsyncClient
) -> List[ExactSpanMatch]:
    if not chunk.sentences:
        return []

    try:
        coarse_hits = await _llm_find_relevant_sentences(chunk, rules, model, client)
    except Exception as e:
        logger.error("Error in coarse sentence selection: %s", e)
        return []

    rule_map = {r.id: r for r in rules}
    sentence_by_id = {s.sid: s for s in chunk.sentences}
    sentence_pos = {s.sid: idx for idx, s in enumerate(chunk.sentences)}

    exact_matches: List[ExactSpanMatch] = []

    for hit in coarse_hits:
        if hit.rule_id not in rule_map:
            continue

        valid_ids = sorted(
            {sid for sid in hit.sentence_ids if sid in sentence_by_id},
            key=lambda sid: sentence_pos[sid]
        )
        if not valid_ids:
            continue

        groups = _group_contiguous_sentence_ids(valid_ids, sentence_pos)

        for group_ids in groups:
            group_sentences = [sentence_by_id[sid] for sid in group_ids]
            local_start = group_sentences[0].token_start
            local_end = group_sentences[-1].token_end

            candidate_tokens = chunk.tokens[local_start:local_end + 1]

            boundary = await _llm_refine_span_boundaries(
                rule=rule_map[hit.rule_id],
                candidate_tokens=candidate_tokens,
                model=model,
                client=client
            )

            if boundary is None:
                exact_matches.append(ExactSpanMatch(
                    rule_id=hit.rule_id,
                    start_token=local_start,
                    end_token=local_end
                ))
                continue

            start_token = local_start + boundary.start_token
            end_token = local_start + boundary.end_token

            if start_token < 0 or end_token >= len(chunk.tokens) or start_token > end_token:
                exact_matches.append(ExactSpanMatch(
                    rule_id=hit.rule_id,
                    start_token=local_start,
                    end_token=local_end
                ))
                continue

            exact_matches.append(ExactSpanMatch(
                rule_id=hit.rule_id,
                start_token=start_token,
                end_token=end_token
            ))

    return exact_matches


async def _llm_find_relevant_sentences(
        chunk: Chunk,
        rules: List[RuleLike],
        model: str,
        client: AsyncClient
) -> List[CoarseMatchResult]:
    rule_descriptions = "\n".join([f'- ID "{r.id}": {r.termsRaw}' for r in rules])
    sentence_block = "\n".join([f"[{s.sid}] {s.text}" for s in chunk.sentences])

    prompt = f"""You are an advanced document analyzer.

Task:
Find which sentences discuss the meaning of each rule.

Rules:
{rule_descriptions}

Instructions:
- Return ONLY sentence IDs from the provided list (e.g. "S3", "S4").
- A rule can match multiple sentences.
- Include all relevant sentences, but do not add unrelated ones.
- Do not return quotes.
- Do not invent sentence IDs.
- If a rule is not present, do not include it.

Sentences:
{sentence_block}
"""

    response = await client.chat(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        format=LLMCoarseResponse.model_json_schema(),
        options={"temperature": 0.0}
    )

    raw = response["message"]["content"]
    data = _parse_json_from_llm(raw)
    parsed = LLMCoarseResponse.model_validate(data)
    return parsed.matches


async def _llm_refine_span_boundaries(
        rule: RuleLike,
        candidate_tokens: List[Token],
        model: str,
        client: AsyncClient
) -> Optional[LLMBoundaryResponse]:
    if not candidate_tokens:
        return None

    token_lines = "\n".join(f"[{i}] {t.text}" for i, t in enumerate(candidate_tokens))
    plain_text = " ".join(t.text for t in candidate_tokens)

    prompt = f"""You are selecting an exact token span that evidences a rule.

Rule:
- ID "{rule.id}": {rule.termsRaw}

Instructions:
- Select the SMALLEST contiguous token span that directly evidences the rule.
- Return token indices only (start_token, end_token).
- The indices refer to the token list below.
- start_token and end_token must be valid and satisfy start_token <= end_token.
- Do not paraphrase. Do not return text.

Candidate text:
{plain_text}

Tokens:
{token_lines}
"""

    try:
        response = await client.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            format=LLMBoundaryResponse.model_json_schema(),
            options={"temperature": 0.0}
        )

        raw = response["message"]["content"]
        data = _parse_json_from_llm(raw)
        parsed = LLMBoundaryResponse.model_validate(data)

        if parsed.start_token < 0 or parsed.end_token < 0:
            return None
        if parsed.start_token > parsed.end_token:
            return None
        if parsed.end_token >= len(candidate_tokens):
            return None

        return parsed

    except Exception as e:
        logger.warning("Boundary refinement failed for rule %s: %s", rule.id, e)
        return None


def _group_contiguous_sentence_ids(
        sentence_ids: List[str],
        sentence_pos: dict[str, int]
) -> List[List[str]]:
    if not sentence_ids:
        return []

    ordered = sorted(sentence_ids, key=lambda sid: sentence_pos[sid])
    groups: List[List[str]] = []
    current_group: List[str] = [ordered[0]]

    for sid in ordered[1:]:
        prev_sid = current_group[-1]
        if sentence_pos[sid] == sentence_pos[prev_sid] + 1:
            current_group.append(sid)
        else:
            groups.append(current_group)
            current_group = [sid]

    groups.append(current_group)
    return groups


def _parse_json_from_llm(raw: str) -> Any:
    raw = raw.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    raw_no_fence = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.IGNORECASE | re.DOTALL).strip()
    try:
        return json.loads(raw_no_fence)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    if match:
        return json.loads(match.group(0))

    raise ValueError(f"Could not parse JSON from LLM response: {raw[:500]}")
