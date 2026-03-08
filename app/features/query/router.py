import logging
from collections.abc import AsyncIterator
from typing import cast

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from ollama import AsyncClient

from core.clients import create_ollama_client
from core.settings import ANSWER_MODEL
from features.query.schemas import (
    ChatTitleIn,
    ChatTitleOut,
    QueryDoneEvent,
    QueryIn,
    QueryUpdateProgressEvent,
    SetSourcesEvent,
    TokenEvent,
    ndjson_query,
)
from features.query.service import (
    format_sources_by_file,
    get_query_hits,
    normalize_sources,
    sanitize_title,
)
from features.prompts.store import get_prompt_content

router = APIRouter(tags=["query"])


@router.post("/api/query")
async def query(body: QueryIn) -> StreamingResponse:
    async def gen() -> AsyncIterator[str]:
        prior_messages = [m for m in (body.messages or []) if m.content.strip()]
        source_list = normalize_sources(body.sources or [])

        yield ndjson_query(QueryUpdateProgressEvent(stage="search_hits"))
        hits = await get_query_hits(body.prompt)
        context, sources = format_sources_by_file(hits, existing_sources=source_list)
        yield ndjson_query(SetSourcesEvent(sources=sources))
        client = create_ollama_client()
        source_context = "SOURCES:\n" + (
            context.strip() if context.strip() else "(none)"
        )
        system_prompt = get_prompt_content("query_system")
        yield ndjson_query(QueryUpdateProgressEvent(stage="generate_start", debug=context))
        chat_messages = [
            {"role": "system", "content": system_prompt},
            {"role": "system", "content": source_context},
            *[
                {"role": m.role, "content": m.content.strip()}
                for m in prior_messages
            ],
            {"role": "user", "content": body.prompt},
        ]

        async for part in await client.chat(
            model=ANSWER_MODEL,
            messages=chat_messages,
            stream=True,
        ):
            token = part.get("message", {}).get("content", "")
            if token:
                yield ndjson_query(TokenEvent(token=token))
        yield ndjson_query(QueryDoneEvent())

    return StreamingResponse(
        gen(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/api/chat-title", response_model=ChatTitleOut)
async def chat_title(
    body: ChatTitleIn,
    ollama_client: AsyncClient = Depends(create_ollama_client),
) -> ChatTitleOut:
    msgs = [m for m in body.messages if m.content.strip()]
    if not msgs:
        return ChatTitleOut(title=None)

    serialized_chat = "\n".join(f"{m.role.upper()}: {m.content.strip()}" for m in msgs[-20:])
    prompt = f"CHAT:\n{serialized_chat}\n\nTITLE:"

    try:
        system_prompt = get_prompt_content("title_system")
        result = await ollama_client.generate(
            model=ANSWER_MODEL,
            prompt=prompt,
            system=system_prompt,
            stream=False,
        )
        raw_title = cast(str, result.get("response", ""))
        return ChatTitleOut(title=sanitize_title(raw_title))
    except Exception as e:
        logging.error(f"Failed to generate chat title: {e}")
        return ChatTitleOut(title=None)
