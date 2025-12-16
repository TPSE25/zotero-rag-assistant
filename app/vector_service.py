from typing import Any, Dict, List, cast
from main import _get_or_create_chroma_collection

class VectorService:
    def add_embeddings(
        self,
        ids: List[str],
        embeddings: List[List[float]],
        documents: List[str],
        metadata: List[dict] | None = None
    ) -> None:
        collection = _get_or_create_chroma_collection()
        collection.add(
            ids=ids,
            embeddings=cast(Any, embeddings),  # Fix error 2
            documents=documents,
            metadatas=metadata  # Fix error 1: changed from metadata to metadatas
        )

    def query(
        self,
        query_embedding: List[float],
        top_k: int = 5
    ) -> Dict[Any, Any]:
        collection = _get_or_create_chroma_collection()
        results = collection.query(
            query_embeddings=cast(Any, [query_embedding]),  # Fix error 3
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
        results = collection.get(include=cast(Any, ["ids"]))  # Fix error 4
        ids = results["ids"]
        return cast(List[str], ids)

    def reset(self) -> None:
        collection = _get_or_create_chroma_collection()
        results = collection.get(include=cast(Any, ["ids"]))  # Fix error 5
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