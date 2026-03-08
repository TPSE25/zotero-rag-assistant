from collections.abc import Mapping, Sequence
from typing import Any, Dict, List, Optional, Tuple, cast

from chromadb.api.types import GetResult, QueryResult

from core.clients import create_ollama_client, get_or_create_chroma_collection
from core.settings import EMBEDDING_MODEL
from core.types import Embedding
from features.query.schemas import Hit, Source


def source_key(source: Source) -> tuple[str, str]:
    return (source.zotero_id, source.filename)


def normalize_sources(existing_sources: List[Source]) -> List[Source]:
    deduped: List[Source] = []
    seen: Dict[tuple[str, str], Source] = {}
    for source in existing_sources:
        key = source_key(source)
        pages = sorted(set(source.pages or [])) or None
        if key in seen:
            merged_pages = sorted(set((seen[key].pages or []) + (pages or []))) or None
            seen[key].pages = merged_pages
            continue
        normalized = Source(
            id=f"S{len(deduped) + 1}",
            filename=source.filename,
            zotero_id=source.zotero_id,
            pages=pages,
        )
        seen[key] = normalized
        deduped.append(normalized)
    return deduped


def _document_id(zotero_id: str, filename: str, idx: int) -> str:
    return f"{zotero_id}_{filename}_{idx}"


def create_hit(doc: str, metadata: Mapping[str, Any]) -> Hit:
    raw_page_start = metadata.get("page_start")
    raw_page_end = metadata.get("page_end")
    page_start = int(raw_page_start) if isinstance(raw_page_start, (int, float)) else None
    page_end = int(raw_page_end) if isinstance(raw_page_end, (int, float)) else None
    return Hit(
        text=doc,
        filename=cast(str, metadata["filename"]),
        zotero_id=cast(str, metadata["zotero_id"]),
        chunk_index=cast(int, metadata["chunk_index"]),
        page_start=page_start,
        page_end=page_end,
    )


def _get_neighbor_ids(hits: List[Hit]) -> set[str]:
    hit_ids = {_document_id(h.zotero_id, h.filename, h.chunk_index) for h in hits}
    neighbor_ids: set[str] = set()
    for h in hits:
        for offset in (-1, 1):
            nid = _document_id(h.zotero_id, h.filename, h.chunk_index + offset)
            if nid not in hit_ids:
                neighbor_ids.add(nid)
    return neighbor_ids


async def get_query_hits(
    prompt: str,
    n_results: int = 12,
    neighbor_top_n: int = 5,
) -> List[Hit]:
    collection = get_or_create_chroma_collection()
    client = create_ollama_client()
    response = await client.embed(model=EMBEDDING_MODEL, input=prompt)
    query_embedding: Embedding = cast(Sequence[float], response.embeddings[0])
    res: QueryResult = collection.query(
        query_embeddings=query_embedding,
        n_results=n_results,
        include=["documents", "metadatas"],
    )
    docs = res["documents"]
    metas = res["metadatas"]
    if docs is None or metas is None:
        return []
    if len(docs) == 0 or len(metas) == 0:
        return []
    docs0 = docs[0]
    metas0 = metas[0]
    hits = [create_hit(doc, metadata) for doc, metadata in zip(docs0, metas0)]
    neighbor_ids = _get_neighbor_ids(hits[: max(neighbor_top_n, 0)])
    if neighbor_ids:
        n_res: GetResult = collection.get(ids=list(neighbor_ids), include=["documents", "metadatas"])
        n_docs = n_res["documents"]
        n_metas = n_res["metadatas"]
        if n_docs is not None and n_metas is not None:
            hits += [create_hit(doc, metadata) for doc, metadata in zip(n_docs, n_metas)]

    return hits


def format_sources_by_file(
    hits: List[Hit],
    existing_sources: Optional[List[Source]] = None,
) -> Tuple[str, List[Source]]:
    prior = normalize_sources(existing_sources or [])
    by_file: Dict[str, Tuple[str, List[Hit]]] = {}
    sources: List[Source] = list(prior)
    key_to_id: Dict[tuple[str, str], str] = {
        source_key(s): s.id for s in sources
    }
    key_to_source: Dict[tuple[str, str], Source] = {
        source_key(s): s for s in sources
    }

    for hit in hits:
        key = (hit.zotero_id, hit.filename)
        if key not in key_to_id:
            sid = f"S{len(sources) + 1}"
            key_to_id[key] = sid
            source = Source(id=sid, filename=hit.filename, zotero_id=hit.zotero_id, pages=[])
            sources.append(source)
            key_to_source[key] = source

        source = key_to_source[key]
        existing_pages = set(source.pages or [])
        if hit.page_start is not None and hit.page_end is not None:
            start_page = min(hit.page_start, hit.page_end)
            end_page = max(hit.page_start, hit.page_end)
            existing_pages.update(range(start_page, end_page + 1))
        elif hit.page_start is not None:
            existing_pages.add(hit.page_start)
        elif hit.page_end is not None:
            existing_pages.add(hit.page_end)
        source.pages = sorted(existing_pages) if existing_pages else None
        group_key = f"{key_to_id[key]}\0{hit.zotero_id}\0{hit.filename}"
        if group_key not in by_file:
            by_file[group_key] = (hit.zotero_id, [])
        by_file[group_key][1].append(hit)

    blocks: List[str] = []

    for group_key, (_zotero_id, excerpts) in by_file.items():
        sid, _key_zotero_id, filename = group_key.split("\0", 2)
        excerpts_formatted = [
            (
                f"(pages {hit.page_start}-{hit.page_end}, chunk {hit.chunk_index}) {hit.text.strip()}"
                if hit.page_start is not None and hit.page_end is not None and hit.page_start != hit.page_end
                else (
                    f"(page {hit.page_start or hit.page_end}, chunk {hit.chunk_index}) {hit.text.strip()}"
                    if (hit.page_start is not None or hit.page_end is not None)
                    else f"(chunk {hit.chunk_index}) {hit.text.strip()}"
                )
            )
            for hit in sorted(excerpts, key=lambda x: x.chunk_index)
        ]

        combined = "\n\n---\n\n".join(excerpts_formatted)
        blocks.append(
            f"[{sid}] filename: {filename}\n"
            f"\"\"\"\n{combined}\n\"\"\""
        )

    return "\n\n".join(blocks), sources


def sanitize_title(raw: str) -> Optional[str]:
    title = " ".join(raw.replace("\n", " ").split()).strip(" \"'`.,;:!?-")
    if len(title) > 80:
        title = title[:80].rstrip()
    if not title:
        return None
    return title
