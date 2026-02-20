from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from typing import Any, List, Optional, Protocol

from ollama import AsyncClient
from pydantic import BaseModel, Field


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
class Chunk:
    text: str
    tokens: List[Token]
    start_index: int  # Index in the full token list

class MatchResult(BaseModel):
    rule_id: str
    quote: str

class LLMResponse(BaseModel):
    matches: List[MatchResult]

async def process_annotations(
    pdf_path: str,
    rules: List[RuleLike],
    answer_model: str,
    ollama_client: AsyncClient
) -> List[dict[str, Any]]:
    """
    Process PDF to find annotations using LLM.
    Returns a list of matches compatible with RagPdfMatch.
    """
    

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
    

    final_matches: List[dict[str, Any]] = []
    
    for chunk, results in zip(chunks, chunk_results):
        for hit in results:
            matched_indices = _find_token_sequence(chunk.tokens, hit.quote)
            
            if matched_indices:
                by_page: dict[int, list[Rect]] = {}
                
                for idx in matched_indices:
                    tok = chunk.tokens[idx]
                    if tok.rect:
                        if tok.page not in by_page:
                            by_page[tok.page] = []
                        by_page[tok.page].append(tok.rect)
                
                for page_idx, rects in by_page.items():
                    final_matches.append({
                        "id": hit.rule_id,
                        "page": page_idx,
                        "rects": rects 
                    })
                    
    return final_matches

def _create_chunks(tokens: List[Token], chunk_size: int, overlap: int) -> List[Chunk]:
    chunks = []

    if len(tokens) <= chunk_size:
        return [Chunk(text=" ".join(t.text for t in tokens), tokens=tokens, start_index=0)]
        
    step = chunk_size - overlap
    if step < 1: step = 1
    
    for i in range(0, len(tokens), step):
        batch = tokens[i : i + chunk_size]
        text = " ".join([t.text for t in batch])
        chunks.append(Chunk(text=text, tokens=batch, start_index=i))

        if len(batch) < overlap and i > 0:
            break
            
    return chunks

async def _process_chunk(
    chunk: Chunk,
    rules: List[RuleLike],
    model: str,
    client: AsyncClient
) -> List[MatchResult]:

    rule_descriptions = "\n".join([f"- ID \"{r.id}\": {r.termsRaw}" for r in rules])
    
    prompt = f"""You are an advanced document analyzer.
    Analyze the provided text fragment for specific concepts.

    Your task is to identify if any of the following rules/concepts are present in the text.
    Crucially, you should look for PASSAGES that discuss the CONCEPT defined by the rule.
    Do not look for synonyms or keywords. Look for the MEANING.
    For example, if the rule is "tests", find any text describing experimental procedures, validation steps, or results analysis.

    Rules to find:
    {rule_descriptions}

    For each rule found:
    1. Identify the concept in the text.
    2. Extract the EXACT, VERBATIM quote from the text that evidences the rule.
    3. The quote should be the *complete sentence(s)* or *passage* that discusses the concept.
    4. Do not just extract the keyword unless it's the only relevant part.
    5. The quote must be an exact substring of the provided text. Do not paraphrase.
    6. If a rule is not found, do not include it.

    Text to analyze:
    {chunk.text}
    """
    
    try:
        print("==Request==")
        print(prompt)
        print("==Request==")
        response = await client.chat(
            model=model,
            messages=[{'role': 'user', 'content': prompt}],
            format=LLMResponse.model_json_schema(),
            options={"temperature": 0.0}
        )
        
        resp_content = response['message']['content']
        print("==Response==")
        print(resp_content)
        print("==Response==")

        data = json.loads(resp_content)
        matches = data.get("matches", [])
        return [MatchResult(rule_id=m["rule_id"], quote=m["quote"]) for m in matches if "rule_id" in m and "quote" in m]
            
    except Exception as e:
        logger.error(f"Error processing chunk with LLM: {e}")
        return []

def _find_token_sequence(tokens: List[Token], quote: str) -> List[int]:
    """
    Finds the indices of tokens that match the quote.
    Uses a fuzzy matching approach to handle whitespace/punctuation differences.
    """

    q_words = [w.lower() for w in re.findall(r"\w+", quote)]
    if not q_words:
        return []
        

    

    t_clean = []
    original_indices = []
    
    for idx, t in enumerate(tokens):
        # Extract alphanumeric parts
        words = [w.lower() for w in re.findall(r"\w+", t.text)]
        for w in words:
            t_clean.append(w)
            original_indices.append(idx)
            


    n = len(q_words)
    m = len(t_clean)
    
    if n > m:
        return []
        

    for i in range(m - n + 1):
        if t_clean[i : i + n] == q_words:
            start_token_idx = original_indices[i]
            end_token_idx = original_indices[i + n - 1]
            
            return list(range(start_token_idx, end_token_idx + 1))
            
    return []
