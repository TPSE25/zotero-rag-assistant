import zipfile
import os
import mimetypes
from typing import Dict
import logging
import pdfplumber
import io

logger = logging.getLogger(__name__)


def extract_from_pdf(file_path_or_bytes) -> str:
    """Extract text from a PDF file (file path or bytes)."""
    try:
        if isinstance(file_path_or_bytes, bytes):
            pdf_file = io.BytesIO(file_path_or_bytes)
        else:
            if not os.path.exists(file_path_or_bytes):
                logger.error(f"PDF not found: {file_path_or_bytes}")
                return ""
            pdf_file = file_path_or_bytes

        with pdfplumber.open(pdf_file) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
            return text

    except Exception as e:
        logger.error(f"Failed to extract PDF: {e}", exc_info=True)
        return ""


def extract_from_zip(file_path: str) -> Dict[str, str]:
    """Extract text and PDFs from a ZIP archive."""
    texts = {}

    if not os.path.exists(file_path):
        logger.error(f"ZIP file not found: {file_path}")
        return texts

    try:
        with zipfile.ZipFile(file_path, 'r') as zip_ref:
            for file_info in zip_ref.infolist():
                if file_info.is_dir():
                    continue

                filename = file_info.filename.lower()

                try:
                    with zip_ref.open(file_info) as file:
                        content_bytes = file.read()

                        if filename.endswith(".txt"):
                            try:
                                content = content_bytes.decode("utf-8")
                                texts[file_info.filename] = content
                            except UnicodeDecodeError:
                                logger.warning(f"Skipping non-UTF8 file: {file_info.filename}")

                        elif filename.endswith(".pdf"):
                            text = extract_from_pdf(content_bytes)
                            texts[file_info.filename] = text

                        else:
                            logger.warning(f"Unsupported file type in ZIP: {file_info.filename}")

                except Exception as e:
                    logger.error(f"Error reading '{file_info.filename}' from ZIP: {e}", exc_info=True)
                    continue

    except zipfile.BadZipFile:
        logger.error(f"Corrupt ZIP file: {file_path}")
    except Exception as e:
        logger.error(f"Failed to open ZIP '{file_path}': {e}", exc_info=True)

    return texts


def extract_auto(file_path: str) -> Dict[str, str]:
    """Automatically detect file type (PDF or ZIP) and extract content."""
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        return {}

    mime_type, _ = mimetypes.guess_type(file_path)

    if not mime_type:
        logger.warning(f"Could not detect MIME type for: {file_path}")
        return {}

    if mime_type == 'application/pdf':
        text = extract_from_pdf(file_path)
        return {os.path.basename(file_path): text}

    elif mime_type == 'application/zip':
        return extract_from_zip(file_path)

    else:
        logger.warning(f"Unsupported MIME type '{mime_type}' for file: {file_path}")
        return {}
