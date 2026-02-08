import pytest
from pathlib import Path
from text_chunking import TextChunker
from file_extractor import extract_from_pdf, extract_from_zip, extract_auto

# Folder with your test files
TEST_FILES_DIR = Path(__file__).parent / "test_data_file_extractor"

pdf_file = TEST_FILES_DIR / "paper.pdf"
txt_file = TEST_FILES_DIR / "paper.txt"
zip_file = TEST_FILES_DIR / "paper.zip"


def _assert_chunking_works(text: str, max_tokens: int = 100)->None:
    chunker = TextChunker()

    # Clean text (TextChunker now handles dicts too)
    cleaned_text = chunker.clean_text(text)
    assert cleaned_text, "Cleaned text should not be empty"

    token_count = chunker.estimate_token_count(cleaned_text)
    assert token_count > 0, "Estimated token count should be positive"

    chunks = chunker.chunk_text(cleaned_text, max_tokens=max_tokens)
    assert chunks, "Chunks should not be empty"

    # Print chunk info
    print(f"\nTotal chunks: {len(chunks)}")
    for i, chunk in enumerate(chunks, 1):
        print(f"Chunk {i} ({chunker.estimate_token_count(chunk)} tokens):")
        # Print first 200 characters of chunk for readability
        print(chunk[:200] + ("..." if len(chunk) > 200 else ""))
        print("-" * 50)

    # Assertions for token limits
    for chunk in chunks:
        assert chunker.estimate_token_count(chunk) <= max_tokens


@pytest.mark.integration
def test_text_chunker_pdf()->None:
    pdf_result = extract_from_pdf(pdf_file)
    _assert_chunking_works(pdf_result)


@pytest.mark.integration
def test_text_chunker_txt()->None:
    txt_result = extract_auto(txt_file)
    _assert_chunking_works(txt_result)


@pytest.mark.integration
def test_text_chunker_zip()->None:
    zip_result = extract_from_zip(zip_file)
    _assert_chunking_works(zip_result)
