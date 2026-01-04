from typing import Any, Dict, List, cast
from main import _get_or_create_chroma_collection

class VectorService:
    def add_embeddings(
        self,
        ids: List[str],
        embeddings: List[List[float]],
        documents: List[str],
        metadata: List[Dict[str, Any]] | None = None  # Changed from List[dict]
    ) -> None:
        collection = _get_or_create_chroma_collection()
        collection.add(
            ids=ids,
            embeddings=cast(Any, embeddings),
            documents=documents,
            metadatas=cast(Any, metadata)  # Add cast here too
        )

    def query(
        self,
        query_embedding: List[float],
        top_k: int = 5
    ) -> Dict[Any, Any]:
        collection = _get_or_create_chroma_collection()
        results = collection.query(
            query_embeddings=cast(Any, [query_embedding]),
            n_results=top_k
        )
        return cast(Dict[Any, Any], results)

    def delete(self, ids: List[str]) -> None:
        collection = _get_or_create_chroma_collection()
        collection.delete(ids=ids)

    def get_count(self) -> int:
        collection = _get_or_create_chroma_collection()
        count = collection.count()
        return cast(int, count)

    def get_all_ids(self) -> List[str]:
        collection = _get_or_create_chroma_collection()
        results = collection.get(include=cast(Any, ["ids"]))
        ids = results["ids"]
        return cast(List[str], ids)

    def reset(self) -> None:
        collection = _get_or_create_chroma_collection()
        results = collection.get(include=cast(Any, ["ids"]))
        ids = cast(List[str], results["ids"])
        if ids:
            collection.delete(ids=ids)

    def health_check(self) -> bool:
        try:
            collection = _get_or_create_chroma_collection()
            _ = collection.count()
            return True
        except Exception:
            return False