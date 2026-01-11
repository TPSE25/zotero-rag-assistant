import pytest
from pathlib import Path
from app.file_extractor import extract_from_pdf, extract_from_zip, extract_auto

# Folder with your test files
TEST_FILES_DIR = Path(__file__).parent / "test_data_file_extractor"

pdf_file = TEST_FILES_DIR / "egg_fried_rice.pdf"
txt_file = TEST_FILES_DIR / "egg_fried_rice.txt"
zip_file = TEST_FILES_DIR / "egg_fried_rice.zip"

# ------------------------------
# Test extract_from_pdf with real PDF
# ------------------------------
def test_extract_from_pdf_real():
    """Test extracting text from a real PDF file."""
    result = extract_from_pdf(pdf_file)
    assert "Egg Fried Rice Recipe" in result
    assert "Ingredients" in result
    assert "Instructions" in result

# ------------------------------
# Test extract_from_zip with real ZIP
# ------------------------------
def test_extract_from_zip_real():
    """Test extracting files from the real ZIP file."""
    result = extract_from_zip(zip_file)

    # Remove macOS hidden files like __MACOSX
    result = {k: v for k, v in result.items() if not k.startswith("__MACOSX")}

    # ZIP should contain PDF and TXT files
    assert "egg_fried_rice.pdf" in result
    assert "egg_fried_rice.txt" in result

    # Check PDF content
    assert "Egg Fried Rice Recipe" in result["egg_fried_rice.pdf"]
    # Check TXT content
    assert "Egg Fried Rice Recipe" in result["egg_fried_rice.txt"]

# ------------------------------
# Test extract_auto with real PDF
# ------------------------------
def test_extract_auto_pdf_real():
    """Test extract_auto for a PDF file."""
    result = extract_auto(pdf_file)
    assert pdf_file.name in result
    assert "Egg Fried Rice Recipe" in result[pdf_file.name]

# ------------------------------
# Test extract_auto with real ZIP
# ------------------------------
def test_extract_auto_zip_real():
    """Test extract_auto for a ZIP file."""
    result = extract_auto(zip_file)

    # Remove macOS hidden files
    result = {k: v for k, v in result.items() if not k.startswith("__MACOSX")}

    assert "egg_fried_rice.pdf" in result
    assert "egg_fried_rice.txt" in result
    assert "Egg Fried Rice Recipe" in result["egg_fried_rice.pdf"]
    assert "Egg Fried Rice Recipe" in result["egg_fried_rice.txt"]

# ------------------------------
# Test extract_auto with real TXT
# ------------------------------
def test_extract_auto_txt_real():
    """Test extract_auto for a TXT file."""
    result = extract_auto(txt_file)
    assert txt_file.name in result
    assert "Egg Fried Rice Recipe" in result[txt_file.name]
