from collections.abc import Mapping, Sequence
from typing import Any, Dict, List, Optional, Tuple, cast

from chromadb.api.types import GetResult, QueryResult

from core.clients import create_ollama_client, get_or_create_chroma_collection
from core.settings import EMBEDDING_MODEL
from core.types import Embedding
from features.query.schemas import Hit, Source


def _document_id(zotero_id: str, filename: str, idx: int) -> str:
    return f"{zotero_id}_{filename}_{idx}"


def create_hit(doc: str, metadata: Mapping[str, Any]) -> Hit:
    return Hit(
        text=doc,
        filename=cast(str, metadata["filename"]),
        zotero_id=cast(str, metadata["zotero_id"]),
        chunk_index=cast(int, metadata["chunk_index"]),
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


def format_sources_by_file(hits: List[Hit]) -> Tuple[str, List[Source]]:
    by_file: Dict[str, Tuple[str, List[Hit]]] = {}

    for hit in hits:
        if hit.filename not in by_file:
            by_file[hit.filename] = (hit.zotero_id, [])
        by_file[hit.filename][1].append(hit)

    blocks: List[str] = []
    sources: List[Source] = []

    for i, (filename, (zotero_id, excerpts)) in enumerate(by_file.items(), start=1):
        sid = f"S{i}"
        sources.append(Source(id=sid, filename=filename, zotero_id=zotero_id))
        excerpts_formatted = [
            f"(chunk {hit.chunk_index}) {hit.text.strip()}"
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
