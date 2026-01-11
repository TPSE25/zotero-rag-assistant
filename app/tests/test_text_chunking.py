import pytest 
from text_chunking import TextChunker

# tests if the whitespace removal works
def test_clean_text_removes_extra_whitespace():
    chunker = TextChunker()
    text = "This   is \n a   test\tstring"

    cleaned = chunker.clean_text(text)

    assert cleaned == "This is a test string"

# tests if whitespaces on the edges are removed
def test_clean_text_edges():
    chunker = TextChunker()
    text = "   test string   "

    assert chunker.clean_text(text) == "test string"

# tests if the token count estimation is larger for a longer text than a shorter one
def test_estimate_token_count():
    chunker = TextChunker()

    short = "one two three"
    long = "one two three four five six"

    assert chunker.estimate_token_count(long) > chunker.estimate_token_count(short)


# tests if the estimation is zero for an empty test
def test_estimate_token_count_empty():
    chunker = TextChunker()

    assert chunker.estimate_token_count("") == 0


# tests if a short sentence is indeed chunked into a single chunk
def test_chunk_text_single_chunk():
    chunker = TextChunker()
    text = "one two three four five six"

    chunks = chunker.chunk_text(text, max_tokens=100)

    assert chunks == ["one two three four five six"]

# tests if the creation of multiple chunks works
def test_chunk_text_multiple_chunks():
    chunker = TextChunker()
    text = "one two three four five six seven eight nine ten"

    chunks = chunker.chunk_text(text, max_tokens=5)

    assert len(chunks) > 1


# tests if the chunker preserves the words of the text and their order
def test_chunk_text_preserves_all_words():
    chunker = TextChunker()
    text = "one two three four five six seven eight nine ten"

    chunks = chunker.chunk_text(text, max_tokens=5)

    reconstructed = " ".join(chunks)

    assert reconstructed.split() == text.split()

# tests if a chunk exceeds the max tokens
def test_chunk_text_respects_max_tokens():
    chunker = TextChunker()
    text = "one two three four five six seven eight nine ten"

    max_tokens = 5
    chunks = chunker.chunk_text(text, max_tokens=max_tokens)

    for chunk in chunks:
        assert chunker.estimate_token_count(chunk) < max_tokens

# tests that there are no empty chunks for a non-empty text
def test_chunk_text_no_empty_chunks():
    chunker = TextChunker()
    text = "one two three four five six seven eight nine ten"

    chunks = chunker.chunk_text(text, max_tokens=5)

    assert all(chunk.strip() != "" for chunk in chunks)

# tests if a single long word exceeds max tokens
def test_single_word_larger_than_max_tokens():
    chunker = TextChunker()
    text = "eierschalensollbruchstellenverursacher"

    chunks = chunker.chunk_text(text, max_tokens=1)

    assert chunks == ["eierschalensollbruchstellenverursacher"]

