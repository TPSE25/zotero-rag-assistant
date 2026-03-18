from __future__ import annotations

import logging
from typing import Any, Optional, TypedDict

import pdfplumber
from pdf2image import convert_from_path
import pytesseract # type: ignore[import-untyped]

# Initialize logger for debugging and warnings
logger = logging.getLogger(__name__)

# Rectangle type: (x0, y0, x1, y1)
Rect = tuple[float, float, float, float]


# Represents a single word and its bounding box (if available)
class WordData(TypedDict):
    text: str                  # The extracted word
    rect: Optional[Rect]       # Bounding box coordinates (None if unavailable)


# Represents a single PDF page and its extracted words
class PageData(TypedDict):
    page: int                  # Page index (0-based)
    page_height: float         # Height of the page (used for coordinate conversion)
    words: list[WordData]      # List of extracted words


class TextPlaceRecognitionPDF:
    def __init__(self, path: str) -> None:
        # Path to the PDF file
        self.pdf_path: str = path
        # Stores extracted data for all pages
        self.pages: list[PageData] = []

    def _is_pdf(self) -> bool:
        """
        Checks whether the file is a valid PDF by reading its header.
        PDF files start with '%PDF-'.
        """
        try:
            with open(self.pdf_path, "rb") as f:
                return f.read(5) == b"%PDF-"
        except Exception as e:
            logger.warning(f"Failed to read PDF header: {e}")
            return False

    def extract_text(self) -> list[PageData]:
        """
        Extracts text and word bounding boxes from the PDF using pdfplumber.
        Falls back to OCR if pdfplumber fails.
        """
        # Validate file type
        if not self._is_pdf():
            logger.error(f"File {self.pdf_path} is not a valid PDF.")
            return []

        # Reset stored pages
        self.pages = []

        try:
            # Open PDF with pdfplumber
            with pdfplumber.open(self.pdf_path) as doc:
                for page_index, page in enumerate(doc.pages):
                    # Get page height (needed for coordinate transformation)
                    page_height = float(page.height)

                    # Extract words with bounding box info
                    words_raw: list[dict[str, Any]] = page.extract_words() or []

                    words: list[WordData] = []
                    for w in words_raw:
                        # Extract word text
                        text = str(w.get("text", ""))

                        # Extract bounding box coordinates
                        x0 = float(w["x0"])
                        x1 = float(w["x1"])
                        top = float(w["top"])
                        bottom = float(w["bottom"])

                        # Convert coordinates:
                        # pdfplumber uses top-left origin,
                        # but many systems use bottom-left origin → flip vertically
                        rect: Rect = (
                            x0,
                            page_height - bottom,
                            x1,
                            page_height - top,
                        )

                        words.append({"text": text, "rect": rect})

                    # Store page data
                    self.pages.append(
                        {
                            "page": page_index,
                            "page_height": page_height,
                            "words": words,
                        }
                    )

        except Exception as e:
            # If structured extraction fails, fallback to OCR
            logger.warning(f"pdfplumber failed: {e}, falling back to OCR")
            self._extract_text_ocr()

        return self.pages

    def _extract_text_ocr(self) -> None:
        """
        Fallback OCR-based text extraction using pytesseract.

        NOTE:
        - Does NOT provide bounding boxes (rect = None).
        - This avoids crashes but prevents highlighting (e.g., in Zotero).
        """
        try:
            # Convert PDF pages to images
            images = convert_from_path(self.pdf_path)

            for page_index, img in enumerate(images):
                # Run OCR on the image
                text = pytesseract.image_to_string(img)

                # Split text into words (no positional data available)
                words: list[WordData] = [
                    {"text": w, "rect": None} for w in text.split()
                ]

                # Store page data
                self.pages.append({
                    "page": page_index,
                    "page_height": float(img.height),
                    "words": words
                })

        except Exception as e:
            logger.error(f"OCR extraction failed: {e}")