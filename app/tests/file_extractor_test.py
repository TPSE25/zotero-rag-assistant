
from pathlib import Path
from app.file_extractor import extract_from_pdf, extract_from_zip, extract_auto

# Folder with your test files
TEST_FILES_DIR = Path(__file__).parent / "test_data_file_extractor"

pdf_file = TEST_FILES_DIR / "paper.pdf"
txt_file = TEST_FILES_DIR / "paper.txt"
zip_file = TEST_FILES_DIR / "paper.zip"


def test_extract_from_pdf_real():
    """Test extracting text from a real PDF file."""
    result = extract_from_pdf(pdf_file)
    
    # Basic checks
    assert result, "Extracted text should not be empty"
    assert len(result) > 1000, "Paper should contain substantial text"
    
    # Title is split across lines in PDF - check parts separately
    assert "Designing a Compositional CRDT" in result
    assert "Collaborative" in result
    assert "Spreadsheets" in result
    
    # Core concepts
    assert "CRDT" in result
    assert "ReplicatedUniqueList" in result
    assert "ObserveRemoveMap" in result
    assert "Bismuth" in result
    
    # Sections
    assert "Implementation" in result
    assert "Google" in result
    assert "Notion" in result


def test_extract_from_zip_real():
    """Test extracting files from the real ZIP file."""
    result = extract_from_zip(zip_file)
    
    # Filter out __MACOSX and empty files
    result = {k: v for k, v in result.items() 
              if not k.startswith("__MACOSX") and v and len(v.strip()) > 0}
    
    assert result, "ZIP should have non-empty files"
    assert len(result) > 0
    
    all_content = " ".join(result.values())
    assert "CRDT" in all_content or "crdt" in all_content.lower()
    assert "spreadsheet" in all_content.lower()


def test_extract_auto_pdf_real():
    """Test extract_auto for a PDF file."""
    result = extract_auto(pdf_file)
    
    assert result
    assert pdf_file.name in result
    content = result[pdf_file.name]
    
    assert len(content) > 1000
    assert "Designing a Compositional CRDT" in content
    assert "Collaborative" in content
    assert "Spreadsheets" in content
    assert "ReplicatedUniqueList" in content


def test_extract_auto_zip_real():
    """Test extract_auto for a ZIP file."""
    result = extract_auto(zip_file)
    
    # Filter out empty files
    result = {k: v for k, v in result.items() 
              if not k.startswith("__MACOSX") and v and len(v.strip()) > 0}
    
    assert result
    assert len(result) > 0
    
    all_content = " ".join(result.values())
    assert "CRDT" in all_content or "crdt" in all_content.lower()


def test_extract_auto_txt_real():
    """Test extract_auto for a TXT file."""
    result = extract_auto(txt_file)
    
    assert result
    assert txt_file.name in result
    content = result[txt_file.name]
    
    assert len(content) > 500
    assert "CRDT" in content or "crdt" in content.lower()
    assert "spreadsheet" in content.lower()
    assert "ReplicatedUniqueList" in content or "replicateduniquelist" in content.lower()


def test_extract_pdf_sections():
    """Test that major sections are extracted."""
    result = extract_from_pdf(pdf_file)
    result_lower = result.lower()
    
    sections = ["Introduction", "Implementation", "Related", "Conclusion"]
    found = sum(1 for s in sections if s.lower() in result_lower)
    assert found >= 3


def test_extract_pdf_technical_terms():
    """Test key technical terms."""
    result = extract_from_pdf(pdf_file)
    result_lower = result.lower()
    
    terms = ["replicateduniquelist", "observeremovemap", "bismuth", 
             "positional", "concurrent", "replica"]
    found = sum(1 for t in terms if t in result_lower)
    assert found >= 5


def test_extract_pdf_references():
    """Test references to systems and researchers."""
    result = extract_from_pdf(pdf_file)
    
    assert "Google" in result or "google" in result.lower()
    assert "Notion" in result
    assert "Bismuth" in result
    assert "Yanakieva" in result or "Kleppmann" in result


def test_extract_pdf_semantic_concepts():
    """Test semantic concepts."""
    result = extract_from_pdf(pdf_file)
    result_lower = result.lower()
    
    concepts = ["concurrent", "conflict", "merge", "replica"]
    found = sum(1 for c in concepts if c in result_lower)
    assert found >= 3


def test_extract_pdf_tables_and_figures():
    """Test table and figure content."""
    result = extract_from_pdf(pdf_file)
    result_lower = result.lower()
    
    # PDF may not preserve exact "Table 1" formatting
    assert "table" in result_lower or "semantics" in result_lower
    assert "figure" in result_lower or "fig" in result_lower


def test_extract_pdf_operations():
    """Test spreadsheet operations."""
    result = extract_from_pdf(pdf_file)
    result_lower = result.lower()
    
    ops = ["insert", "remove", "move", "edit", "undo", "merge"]
    found = sum(1 for op in ops if op in result_lower)
    assert found >= 5
    assert "move" in result_lower
    assert "undo" in result_lower


def test_extract_pdf_algorithm_details():
    """Test algorithmic details."""
    result = extract_from_pdf(pdf_file)
    result_lower = result.lower()
    
    terms = ["filter", "timestamp", "precedence", "element", "operation"]
    found = sum(1 for t in terms if t in result_lower)
    assert found >= 4


def test_extract_pdf_data_structures():
    """Test data structures."""
    result = extract_from_pdf(pdf_file)
    result_lower = result.lower()
    
    structures = ["list", "map", "set"]
    found = sum(1 for s in structures if s in result_lower)
    assert found >= 2


def test_extract_pdf_publication_info():
    """Test publication info."""
    result = extract_from_pdf(pdf_file)
    result_lower = result.lower()
    
    assert "acm" in result_lower
    assert "2026" in result
    assert "copyright" in result_lower


def test_extract_pdf_content_length():
    """Test content length."""
    result = extract_from_pdf(pdf_file)
    
    assert len(result) > 3000
    assert len(result) < 500000
    
    word_count = len(result.split())
    assert word_count > 500


def test_extract_pdf_markers_ranges():
    """Test marker and range concepts."""
    result = extract_from_pdf(pdf_file)
    result_lower = result.lower()
    
    assert "marker" in result_lower or "anchor" in result_lower
    assert "range" in result_lower


def test_extract_pdf_cell_references():
    """Test cell references."""
    result = extract_from_pdf(pdf_file)
    result_lower = result.lower()
    
    assert "cell" in result_lower or "formula" in result_lower


def test_extract_pdf_table_operations():
    """Test table operations."""
    result = extract_from_pdf(pdf_file)
    result_lower = result.lower()
    
    ops = ["edit", "insert", "remove", "move"]
    found = sum(1 for op in ops if op in result_lower)
    assert found >= 3