from __future__ import annotations

import logging
from typing import Any, Optional, Protocol, Sequence, TypedDict, TypeAlias

import pdfplumber
from pdf2image import convert_from_path
import pytesseract # type: ignore[import-untyped]

logger = logging.getLogger(__name__)

Rect: TypeAlias = tuple[float, float, float, float]


class WordData(TypedDict):
    text: str
    rect: Optional[Rect]


class PageData(TypedDict):
    page: int
    page_height: float
    words: list[WordData]


class PlaceMatch(TypedDict):
    id: Any
    place: str
    page: int
    rects: list[Optional[Rect]]


class RuleLike(Protocol):
    id: Any
    termsRaw: str


class TextPlaceRecognitionPDF:
    def __init__(self, path: str) -> None:
        self.pdf_path: str = path
        self.pages: list[PageData] = []

    def _is_pdf(self) -> bool:
        """Check if file starts with %PDF- header"""
        try:
            with open(self.pdf_path, "rb") as f:
                header = f.read(5)
            return header == b"%PDF-"
        except Exception as e:
            logger.warning(f"Failed to read PDF header: {e}")
            return False

    def extract_text(self) -> list[PageData]:
        """Extract words from PDF using pdfplumber or OCR fallback."""
        if not self._is_pdf():
            logger.error(f"File {self.pdf_path} is not a valid PDF.")
            return []

        self.pages = []

        try:
            with pdfplumber.open(self.pdf_path) as doc:
                if not doc.pages:
                    raise ValueError("PDF has no pages")

                for page_index, page in enumerate(doc.pages):
                    page_height = float(page.height)

                    words_raw: list[dict[str, Any]] = page.extract_words() or []

                    words: list[WordData] = []
                    for w in words_raw:
                        text = str(w.get("text", ""))
                        x0 = float(w["x0"])
                        x1 = float(w["x1"])
                        top = float(w["top"])
                        bottom = float(w["bottom"])

                        rect: Rect = (
                            x0,
                            page_height - bottom,
                            x1,
                            page_height - top,
                        )
                        words.append({"text": text, "rect": rect})

                    self.pages.append(
                        {
                            "page": page_index,
                            "page_height": page_height,
                            "words": words,
                        }
                    )

        except Exception as e:
            logger.warning(f"pdfplumber failed: {e}, falling back to OCR")
            self._extract_text_ocr()

        return self.pages

    def _extract_text_ocr(self) -> None:
        """Fallback OCR extraction for scanned/corrupt PDFs."""
        try:
            images = convert_from_path(self.pdf_path)
            for page_index, img in enumerate(images):
                text = pytesseract.image_to_string(img)
                words: list[WordData] = [{"text": w, "rect": None} for w in text.split()]

                self.pages.append({
                    "page": page_index,
                    "page_height": float(img.height),
                    "words": words
                })
        except Exception as e:
            logger.error(f"OCR extraction failed: {e}")

    def recognize_places(self, pages: Sequence[PageData], rules: Sequence[RuleLike]) -> list[PlaceMatch]:
        """Search pages for matching terms."""
        results: list[PlaceMatch] = []
        for page in pages:
            for word in page["words"]:
                text = word["text"].strip()
                if len(text) < 2:
                    continue

                val = text.lower()
                for rule in rules:
                    term = rule.termsRaw.lower().strip()
                    if term == val or (len(term) > 3 and term in val):
                        results.append({
                            "id": rule.id,
                            "place": text,
                            "page": page["page"],
                            "rects": [word["rect"]]
                        })
        return results

    def process_pdf(self, rules: Sequence[RuleLike]) -> list[PlaceMatch]:
        """Full pipeline: extract text and match rules."""
        pages = self.extract_text()
        return self.recognize_places(pages, rules)
