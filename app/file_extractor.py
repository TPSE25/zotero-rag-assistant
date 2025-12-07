import zipfile
import os
from pypdf import PdfReader
def extract_from_pdf(file_path: str) -> str:
	reader = PdfReader(file_path)
	text = ""
	for page in reader.pages:
		text += page.extract_text()
	return text
