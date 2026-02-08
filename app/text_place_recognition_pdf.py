import pdfplumber
from pdf2image import convert_from_path
import pytesseract
import logging

logger = logging.getLogger(__name__)

class TextPlaceRecognitionPDF:
    def __init__(self, path: str):
        self.pdf_path = path
        self.pages = []

    def _is_pdf(self) -> bool:
        """Check if file starts with %PDF- header"""
        try:
            with open(self.pdf_path, "rb") as f:
                header = f.read(5)
            return header == b"%PDF-"
        except Exception as e:
            logger.warning(f"Failed to read PDF header: {e}")
            return False

    def extract_text(self):
        """Extract words from PDF using pdfplumber or OCR fallback."""
        if not self._is_pdf():
            logger.error(f"File {self.pdf_path} is not a valid PDF.")
            return []

        try:
            with pdfplumber.open(self.pdf_path) as doc:
                if not doc.pages:
                    raise ValueError("PDF has no pages")
                for page_index, page in enumerate(doc.pages):
                    page_height = page.height
                    words = page.extract_words()
                    self.pages.append({
                        "page": page_index,
                        "page_height": page_height,
                        "words": [
                            {
                                "text": w["text"],
                                "rect": [
                                    w["x0"],
                                    page_height - w["bottom"],
                                    w["x1"],
                                    page_height - w["top"]
                                ]
                            } for w in words
                        ]
                    })
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
                words = [{"text": w, "rect": None} for w in text.split()]
                self.pages.append({
                    "page": page_index,
                    "page_height": img.height,
                    "words": words
                })
        except Exception as e:
            logger.error(f"OCR extraction failed: {e}")

    def recognize_places(self, pages, rules):
        """Search pages for matching terms."""
        results = []
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

    def process_pdf(self, rules):
        """Full pipeline: extract text and match rules."""
        pages = self.extract_text()
        return self.recognize_places(pages, rules)
