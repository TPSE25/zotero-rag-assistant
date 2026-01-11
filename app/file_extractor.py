import os
import zipfile
import mimetypes
import logging
from typing import Dict, Union
from pathlib import Path  # Add this import
import pdfplumber
from io import BytesIO

# Configure logger
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

def extract_from_pdf(file_path_or_bytes: Union[str, bytes, Path]) -> str:
    try:
        # Ensure pdf_file is always a BytesIO
        if isinstance(file_path_or_bytes, bytes):
            pdf_file = BytesIO(file_path_or_bytes)
        elif isinstance(file_path_or_bytes, (str, Path)):
            file_path = str(file_path_or_bytes)  # Convert Path to str if needed
            if not os.path.exists(file_path):
                logger.error(f"PDF not found: {file_path}")
                return ""
            with open(file_path, "rb") as f:
                pdf_file = BytesIO(f.read())
        else:
            logger.error("Input must be bytes or file path string")
            return ""

        # Extract text using pdfplumber
        with pdfplumber.open(pdf_file) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        return text
    except Exception as e:
        logger.error(f"Failed to extract PDF: {e}", exc_info=True)
        return ""

def extract_from_zip(zip_path: Union[str, Path]) -> Dict[str, str]:
    zip_path = str(zip_path)  # Convert Path to str if needed
    if not os.path.exists(zip_path):
        logger.error(f"ZIP file not found: {zip_path}")
        return {}
    
    result = {}
    try:
        with zipfile.ZipFile(zip_path, "r") as zipf:
            for info in zipf.infolist():
                if info.is_dir() or info.filename.startswith("__MACOSX"):
                    continue
                with zipf.open(info) as f:
                    if info.filename.lower().endswith(".pdf"):
                        try:
                            result[info.filename] = extract_from_pdf(f.read())
                        except Exception as e:
                            logger.error(f"Failed to extract PDF: {e}")
                            result[info.filename] = ""
                    elif info.filename.lower().endswith(".txt"):
                        result[info.filename] = f.read().decode("utf-8")
    except Exception as e:
        logger.error(f"Failed to extract ZIP: {e}")
    return result

def extract_auto(file_path: Union[str, Path]) -> Dict[str, str]:
    file_path_str = str(file_path)  # Convert Path to str if needed
    if not os.path.exists(file_path_str):
        logger.error(f"File not found: {file_path_str}")
        return {}
    
    mime_type, _ = mimetypes.guess_type(file_path_str)
    
    if mime_type == "application/pdf":
        return {os.path.basename(file_path_str): extract_from_pdf(file_path_str)}
    elif mime_type == "application/zip":
        return extract_from_zip(file_path_str)
    elif mime_type == "text/plain":
        try:
            with open(file_path_str, "r", encoding="utf-8") as f:
                return {os.path.basename(file_path_str): f.read()}
        except Exception as e:
            logger.error(f"Failed to read TXT: {file_path_str} - {e}")
            return {}
    else:
        logger.warning(f"Unsupported MIME type '{mime_type}' for file: {file_path_str}")
        return {}