from typing import List
from app.main import _get_or_create_chroma_collection


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
            embeddings=embeddings,
            documents=documents,
            metadata=metadata
        )

    def query(
        self,
        query_embedding: List[float],
        top_k: int = 5
    ) -> dict:
        collection = _get_or_create_chroma_collection()
        return collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k
        )

    def delete(self, ids: List[str]) -> None:
        collection = _get_or_create_chroma_collection()
        collection.delete(ids=ids)

    def get_count(self) -> int:
        collection = _get_or_create_chroma_collection()
        return collection.count()

    def get_all_ids(self) -> List[str]:
        collection = _get_or_create_chroma_collection()
        results = collection.get(include=["ids"])
        return results["ids"]

    def reset(self) -> None:
        collection = _get_or_create_chroma_collection()
        all_ids = collection.get(include=["ids"])["ids"]
        if all_ids:
            collection.delete(ids=all_ids)

    def health_check(self) -> bool:
        try:
            collection = _get_or_create_chroma_collection()
            _ = collection.count()
            return True
        except Exception:
            return False
