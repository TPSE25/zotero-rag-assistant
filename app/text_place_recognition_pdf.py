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
        try:
            with open(self.pdf_path, "rb") as f:
                return f.read(5) == b"%PDF-"
        except Exception as e:
            logger.warning(f"Failed to read PDF header: {e}")
            return False

    def extract_text(self):
        if not self._is_pdf():
            logger.error(f"File {self.pdf_path} is not a valid PDF.")
            return []

        try:
            with pdfplumber.open(self.pdf_path) as doc:
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

    def _extract_text_ocr(self):
        """Note: OCR currently returns rect: None. 
        Zotero cannot highlight without rects, but this prevents a crash."""
        try:
            images = convert_from_path(self.pdf_path)
            for page_index, img in enumerate(images):
                text = pytesseract.image_to_string(img)
                words = [{"text": w, "rect": None} for w in text.split()]
                self.pages.append({
                    "page": page_index, "page_height": img.height, "words": words
                })
        except Exception as e:
            logger.error(f"OCR extraction failed: {e}")

    def recognize_places(self, pages, rules):
        """Optimized search for large documents."""
        results = []
        
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
                            if not word.get("rect"): continue
                            
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

    def process_pdf(self, rules):
        pages = self.extract_text()
        return self.recognize_places(pages, rules)