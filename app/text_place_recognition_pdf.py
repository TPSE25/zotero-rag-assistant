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
        try:
            with open(self.pdf_path, "rb") as f:
                return f.read(5) == b"%PDF-"
        except Exception as e:
            logger.warning(f"Failed to read PDF header: {e}")
            return False

    def extract_text(self) -> list[PageData]:
        if not self._is_pdf():
            logger.error(f"File {self.pdf_path} is not a valid PDF.")
            return []

        self.pages = []

        try:
            with pdfplumber.open(self.pdf_path) as doc:
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
        """Note: OCR currently returns rect: None.
        Zotero cannot highlight without rects, but this prevents a crash."""
        try:
            images = convert_from_path(self.pdf_path)
            for page_index, img in enumerate(images):
                text = pytesseract.image_to_string(img)
                words: list[WordData] = [{"text": w, "rect": None} for w in text.split()]

                self.pages.append({
                    "page": page_index, "page_height": float(img.height), "words": words
                })
        except Exception as e:
            logger.error(f"OCR extraction failed: {e}")

    def recognize_places(self, pages: Sequence[PageData], rules: Sequence[RuleLike]) -> list[PlaceMatch]:
        """Optimized search for large documents."""
        results: list[PlaceMatch] = []

        # 1. Pre-process rules ONCE (Major performance win for large papers)
        processed_rules = []
        for rule in rules:
            keywords = [k.strip().lower() for k in rule.termsRaw.split(",") if k.strip()]
            processed_rules.append({"id": rule.id, "keywords": keywords})
        for page in pages:
            page_words = page["words"]
            # 2. Create a 'flat' version of page text for a quick initial check
            page_text_lower = " ".join([w["text"] for w in page_words]).lower()

            for rule_data in processed_rules:
                matched_rects = []

                for term in rule_data["keywords"]:
                    # 3. Only loop through word objects if the term exists on the page
                    if term in page_text_lower:
                        for word in page_words:
                            if not word.get("rect"):
                                continue

                            word_text = word["text"].lower()
                            # Exact match or substring match for longer terms
                            if term == word_text or (len(term) > 3 and term in word_text):
                                matched_rects.append(word["rect"])

                if matched_rects:
                    results.append({
                        "id": rule_data["id"],
                        "page": page["page"],
                        "rects": matched_rects # Group all rects for this rule on this page
                    })
        return results

    def process_pdf(self, rules: Sequence[RuleLike]) -> list[PlaceMatch]:
        pages = self.extract_text()
        return self.recognize_places(pages, rules)