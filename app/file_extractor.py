import zipfile
import os
import mimetypes
from typing import Dict
import logging
import pdfplumber
logger = logging.getLogger(__name__)

def extract_from_pdf(file_path: str) -> str:
    try:
        if not os.path.exists(file_path):
            logger.error(f"PDF not found: {file_path}")
            return ""

        with pdfplumber.open(file_path) as pdf:
            text = "\n".join(
                (page.extract_text() or "") for page in pdf.pages
        )
        return text

    except Exception as e:
        logger.error(f"Failed to extract PDF '{file_path}': {e}", exc_info=True)
        return ""

    
def extract_from_zip(file_path:str)->Dict[str, str]:
    texts = {}
    with zipfile.ZipFile(file_path, 'r') as zip_ref:
        for file_info in zip_ref.infolist():
            if not file_info.is_dir():
                with zip_ref.open(file_info) as file:
                    try:
                        content = file.read().decode('utf-8')
                        texts[file_info.filename] = content
                    except UnicodeDecodeError:
                        continue
    return texts

def extract_auto(file_path: str) -> Dict[str, str]:
    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type:
        if mime_type == 'application/pdf':
            text = extract_from_pdf(file_path)
            return {os.path.basename(file_path): text}
        elif mime_type == 'application/zip':
            return extract_from_zip(file_path)
        else:
            logging.warning(f"Unsupported MIME type: {mime_type}")
            return {}