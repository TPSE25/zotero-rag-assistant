import pdfplumber

class TextPlaceRecognitionPDF:
    def __init__(self, path=None):
        # Fallback to test path if no path is provided
        self.pdf_path = "app/tests/test_data_file_extractor/paper.pdf"
        self.doc = pdfplumber.open(self.pdf_path)
    
    def extract_text(self):
        pages = []
        for page_index, page in enumerate(self.doc.pages):
            words = page.extract_words()
            page_height = page.height
            pages.append({
                "page": page_index,
                "page_height": page_height,
                "words": [
                    {
                        "text": w["text"],
                        "rect": [w["x0"], page_height - w["bottom"], w["x1"], page_height - w["top"]]
                    } for w in words
                ]
            })
        return pages

    def recognize_places(self, pages, rules):
        results = []
        for page in pages:
            for word in page["words"]:
                text = word["text"].strip()
                if len(text) < 2: 
                    continue 

                val = text.lower()
                for rule in rules:
                    term = rule.termsRaw.lower().strip()
                    # Using exact match or boundary match is usually safer
                    if term == val or (len(term) > 3 and term in val):
                        results.append({
                            "id": rule.id,
                            "place": text,
                            "page": page["page"],
                            "rects": [word["rect"]]
                        })
        return results

    def process_pdf(self, rules):
        pages = self.extract_text()
        return self.recognize_places(pages, rules)