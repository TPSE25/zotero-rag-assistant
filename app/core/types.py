from collections.abc import Mapping, Sequence

from chromadb.api.types import SparseVector

MetadataValue = str | int | float | bool | SparseVector | None
ChromaMetadata = Mapping[str, MetadataValue]
Embedding = Sequence[float] | Sequence[int]
