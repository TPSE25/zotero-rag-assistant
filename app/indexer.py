# indexer.py
import os
from typing import List
from dataclasses import dataclass

# Minimal stubs for missing imports
@dataclass
class DataItem:
    content: str
    source: str

class DocumentConverter:
    def convert(self, path: str) -> "Document":
        return Document(path)

class HybridChunker:
    def chunk(self, document: "Document") -> List["DocChunk"]:
        return []

@dataclass
class Document:
    path: str
    document: str = ""

@dataclass
class DocChunkMeta:
    origin: Document
    headings: List[str]

@dataclass
class DocChunk:
    text: str
    meta: DocChunkMeta

class Indexer:
    def __init__(self) -> None:
        self.converter = DocumentConverter()
        self.chunker = HybridChunker()
        os.environ["TOKENIZERS_PARALLELISM"] = "false"

    def index(self, document_paths: List[str]) -> List[DataItem]:
        items: List[DataItem] = []
        for document_path in document_paths:
            chunks: List[DocChunk] = self.chunker.chunk(Document(document_path))
            items.extend(self._items_from_chunks(chunks))
        return items

    def _items_from_chunks(self, chunks: List[DocChunk]) -> List[DataItem]:
        items: List[DataItem] = []
        for i, chunk in enumerate(chunks):
            content_headings = "## " + ", ".join(chunk.meta.headings)
            content_text = f"{content_headings}\n{chunk.text}"
            source = f"{chunk.meta.origin.path}:{i}"
            items.append(DataItem(content=content_text, source=source))
        return items
