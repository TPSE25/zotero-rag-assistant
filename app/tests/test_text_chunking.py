import pytest 
from text_chunking import TextChunker

def test_clean_text_removes_extra_whitespace():
    chunker = TextChunker()
    text = "This   is \n a   test\tstring"

    cleaned = chunker.clean_text(text)

    assert cleaned == "This is a test string"
