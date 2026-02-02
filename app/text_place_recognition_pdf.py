import pymupdf # PyMuPDF
import hashlib

class TextPlaceRecognitionPDF:
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.doc = pymupdf.open(pdf_path)

    def extract_text(self):
        """Extract words with page info and bounding boxes."""
        pages = []

        for page_index, page in enumerate(self.doc):
            words = page.get_text("words")
            pages.append({
                "page": page_index,
                "words": [
                    {
                        "text": w[4],
                        "rect": (w[0], w[1], w[2], w[3])
                    }
                    for w in words
                ]
            })

        return pages

    def is_place(self, token: str) -> bool:
        """Simple placeholder: capitalize = potential place."""
        # Replace with NER later
        return token.istitle() and token.isalpha()

    def recognize_places(self, pages):
        """
        Recognize places and merge multi-word consecutive capitalized words.
        Returns: list of dicts: {id, place, page, rects}
        """
        results = []

        for page in pages:
            words = page["words"]
            i = 0
            while i < len(words):
                word = words[i]
                if self.is_place(word["text"]):
                    # Start a new multi-word place
                    place_words = [word["text"]]
                    rects = [word["rect"]]
                    i += 1

                    # Merge consecutive capitalized words
                    while i < len(words) and self.is_place(words[i]["text"]):
                        place_words.append(words[i]["text"])
                        rects.append(words[i]["rect"])
                        i += 1

                    place_text = " ".join(place_words)
                    # Generate a stable ID using hash
                    place_id = hashlib.md5(place_text.encode("utf-8")).hexdigest()

                    results.append({
                        "id": place_id,
                        "place": place_text,
                        "page": page["page"],
                        "rects": rects
                    })
                else:
                    i += 1

        return results

    def process_pdf(self):
        pages = self.extract_text()
        places = self.recognize_places(pages)
        return places
