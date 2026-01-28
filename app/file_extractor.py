# file_extractor.py
import zipfile
import mimetypes
import logging
import re
from typing import Dict, Union, BinaryIO
from pathlib import Path
from io import BytesIO

import pdfplumber

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


HEADER_FOOTER_RE = re.compile(
    r"""
    ^\s*\d+\s*$|                              # page numbers
    ACM\s+Reference\s+Format.*|               # ACM boilerplate
    Permission\s+to\s+make\s+digital.*|       # copyright
    ©\d{4}.*ACM.*                             # copyright
    """,
    re.IGNORECASE | re.MULTILINE | re.VERBOSE,
)


def extract_from_pdf(file_path_or_bytes: Union[str, bytes, Path]) -> str:
    """Extract text from a PDF for RAG, including tables and figure captions."""
    try:
        # Normalize input
        if isinstance(file_path_or_bytes, bytes):
            pdf_file = BytesIO(file_path_or_bytes)
        else:
            path = Path(file_path_or_bytes)
            if not path.exists():
                logger.error(f"PDF not found: {path}")
                return ""
            pdf_file = BytesIO(path.read_bytes())

        pages = []

        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                page_text = ""

                # 1. Extract regular text
                text = page.extract_text(layout=True)
                if text:
                    page_text += text + "\n"

                # 2. Extract tables as text
                tables = page.extract_tables()
                for table in tables:
                    table_text = " | ".join([" | ".join(cell if cell else "" for cell in row) for row in table])
                    if table_text.strip():
                        page_text += "\n[Table] " + table_text + "\n"

                # 3. Extract figure captions
                if text:
                    for line in text.splitlines():
                        if re.match(r"^\s*(Figure|Fig)\.?\s*\d+[:.\s]", line, re.IGNORECASE):
                            page_text += "\n[Figure] " + line.strip() + "\n"

                if page_text.strip():
                    pages.append(page_text.strip())

        combined_text = "\n\n".join(pages)
        return clean_pdf_text(combined_text)

    except Exception as e:
        logger.error(f"Failed to extract PDF: {e}", exc_info=True)
        return ""


def clean_pdf_text(text: str) -> str:
    """Clean PDF text for RAG: remove headers/footers, fix hyphenation, normalize whitespace."""
    # Remove headers/footers
    text = HEADER_FOOTER_RE.sub("", text)

    # Fix hyphenated line breaks
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)

    # Join broken lines (PDF column artifacts)
    text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)

    # Normalize whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n\n", text)

    return text.strip()


def extract_from_zip(zip_path: Union[str, Path]) -> Dict[str, str]:
    """Extract all files from a ZIP. PDFs are processed with RAG-aware extraction."""
    zip_path = Path(zip_path)
    if not zip_path.exists():
        logger.error(f"ZIP not found: {zip_path}")
        return {}

    results = {}

    try:
        with zipfile.ZipFile(zip_path, "r") as zipf:
            for info in zipf.infolist():
                if info.is_dir() or info.filename.startswith("__MACOSX"):
                    continue

                name = info.filename
                logger.info(f"Extracting: {name}")

                with zipf.open(info) as f:
                    if name.lower().endswith(".pdf"):
                        results[name] = extract_from_pdf(f.read())
                    elif name.lower().endswith(".txt"):
                        try:
                            results[name] = f.read().decode("utf-8")
                        except UnicodeDecodeError:
                            results[name] = f.read().decode("latin-1", errors="ignore")
                    else:
                        # skip other files
                        continue

    except Exception as e:
        logger.error(f"Failed to process ZIP: {e}", exc_info=True)

    return results


def extract_auto(file_path: Union[str, Path]) -> Dict[str, str]:
    """Automatically detect file type (PDF, ZIP, TXT) and extract content accordingly."""
    file_path = Path(file_path)
    if not file_path.exists():
        logger.error(f"File not found: {file_path}")
        return {}

    mime, _ = mimetypes.guess_type(file_path)

    if mime == "application/pdf":
        return {file_path.name: extract_from_pdf(file_path)}
    elif mime == "application/zip":
        return extract_from_zip(file_path)
    elif mime == "text/plain":
        try:
            return {file_path.name: file_path.read_text(encoding="utf-8")}
        except UnicodeDecodeError:
            return {file_path.name: file_path.read_text(encoding="latin-1", errors="ignore")}
    else:
        logger.warning(f"Unsupported MIME type: {mime}")
        return {}
