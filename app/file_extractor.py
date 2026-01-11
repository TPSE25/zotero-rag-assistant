import os
import zipfile
import mimetypes
import logging
from typing import Dict, Union
from pathlib import Path
import pdfplumber
from io import BytesIO

# Configure logger
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)


def extract_from_pdf(file_path_or_bytes: Union[str, bytes, Path]) -> str:
    """
    Extract text from a PDF file.
    
    Args:
        file_path_or_bytes: Path to PDF file, or bytes content
        
    Returns:
        Extracted text as string, or empty string on failure
    """
    try:
        # Ensure pdf_file is always a BytesIO
        if isinstance(file_path_or_bytes, bytes):
            pdf_file = BytesIO(file_path_or_bytes)
        elif isinstance(file_path_or_bytes, (str, Path)):
            file_path = str(file_path_or_bytes)
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
        
        if not text or len(text.strip()) == 0:
            logger.warning("PDF extraction resulted in empty text")
        
        return text
    except Exception as e:
        logger.error(f"Failed to extract PDF: {e}", exc_info=True)
        return ""


def extract_from_zip(zip_path: Union[str, Path]) -> Dict[str, str]:
    """
    Extract all PDF and TXT files from a ZIP archive.
    
    Args:
        zip_path: Path to ZIP file
        
    Returns:
        Dictionary mapping filenames to extracted content
    """
    zip_path = str(zip_path)
    if not os.path.exists(zip_path):
        logger.error(f"ZIP file not found: {zip_path}")
        return {}
    
    result = {}
    try:
        with zipfile.ZipFile(zip_path, "r") as zipf:
            for info in zipf.infolist():
                # Skip directories and macOS metadata
                if info.is_dir() or info.filename.startswith("__MACOSX"):
                    continue
                
                filename = info.filename
                logger.info(f"Processing file from ZIP: {filename}")
                
                try:
                    with zipf.open(info) as f:
                        if filename.lower().endswith(".pdf"):
                            content = extract_from_pdf(f.read())
                            result[filename] = content
                            if not content:
                                logger.warning(f"PDF extraction resulted in empty content: {filename}")
                        elif filename.lower().endswith(".txt"):
                            try:
                                content = f.read().decode("utf-8")
                                result[filename] = content
                                if not content or len(content.strip()) == 0:
                                    logger.warning(f"TXT file is empty: {filename}")
                            except UnicodeDecodeError:
                                logger.warning(f"UTF-8 decode failed for {filename}, trying latin-1")
                                f.seek(0)
                                content = f.read().decode("latin-1", errors="ignore")
                                result[filename] = content
                        else:
                            logger.debug(f"Skipping unsupported file type: {filename}")
                except Exception as e:
                    logger.error(f"Failed to extract {filename} from ZIP: {e}", exc_info=True)
                    result[filename] = ""
    except zipfile.BadZipFile as e:
        logger.error(f"Invalid ZIP file: {zip_path} - {e}")
    except Exception as e:
        logger.error(f"Failed to process ZIP: {zip_path} - {e}", exc_info=True)
    
    return result


def extract_auto(file_path: Union[str, Path]) -> Dict[str, str]:
    """
    Automatically detect file type and extract content.
    
    Args:
        file_path: Path to file (PDF, ZIP, or TXT)
        
    Returns:
        Dictionary mapping filenames to extracted content
    """
    file_path_str = str(file_path)
    
    if not os.path.exists(file_path_str):
        logger.error(f"File not found: {file_path_str}")
        return {}
    
    mime_type, _ = mimetypes.guess_type(file_path_str)
    logger.info(f"Processing file: {file_path_str} (MIME type: {mime_type})")
    
    if mime_type == "application/pdf":
        content = extract_from_pdf(file_path_str)
        return {os.path.basename(file_path_str): content}
    
    elif mime_type == "application/zip":
        return extract_from_zip(file_path_str)
    
    elif mime_type == "text/plain":
        try:
            try:
                with open(file_path_str, "r", encoding="utf-8") as f:
                    content = f.read()
            except UnicodeDecodeError:
                logger.warning(f"UTF-8 decode failed for {file_path_str}, trying latin-1")
                with open(file_path_str, "r", encoding="latin-1", errors="ignore") as f:
                    content = f.read()
            
            if not content or len(content.strip()) == 0:
                logger.warning(f"TXT file is empty: {file_path_str}")
            
            return {os.path.basename(file_path_str): content}
        except Exception as e:
            logger.error(f"Failed to read TXT: {file_path_str} - {e}", exc_info=True)
            return {}
    
    else:
        logger.warning(f"Unsupported MIME type '{mime_type}' for file: {file_path_str}")
        return {}