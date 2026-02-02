import pytest 
from text_chunking import TextChunker

"""
This tests the text chunker.
Each of the test cases come with several different cases that are tested.
More can be added if necessary at any time.
"""

# tests if the whitespace removal works
@pytest.mark.parametrize("text, expected", [
    ("This   is \n a   test\tstring", "This is a test string"),
    ("  Hey   you! \n \n What    are you   \n doing? ", "Hey you! What are you doing?"),
    ("   When you   \n play    the Game \t of   Thrones you   win or \n \n \n you  die.   ", "When you play the Game of Thrones you win or you die."),
    ("    Nymeria    ", "Nymeria"),
    ("Jon Snow", "Jon Snow")
])
def test_clean_text_removes_extra_whitespace(text, expected):
    chunker = TextChunker()

    cleaned = chunker.clean_text(text)

    assert cleaned == expected

# tests if the token count estimation is larger for a longer text than a shorter one
@pytest.mark.parametrize("short, long", [
    ("Hello there.", "When you play the Game of Thrones you win or you die."),
    ("Thats what I do: I drink and I know things.", "Never forget what you are, the rest of the world will not. Wear it like armor, and it can never be used to hurt you."),
    ("Liar!", "I have the high ground!"),
    ("Liar!", "Hello there.")
])
def test_estimate_token_count(short, long):
    chunker = TextChunker()

    assert chunker.estimate_token_count(long) > chunker.estimate_token_count(short)


# tests if the estimation is zero for an empty text
@pytest.mark.parametrize("text", [" ", "", "    ", "\n  ", "\t"])
def test_estimate_token_count_empty(text):
    chunker = TextChunker()

    assert chunker.estimate_token_count(text) == 0


# tests if a short sentence is indeed chunked into a single chunk
@pytest.mark.parametrize("text", [
    "Short sentence",
    "Hello there",
    "I have the high ground!",
    "Valar morghulis"
])
def test_chunk_text_single_chunk(text):
    chunker = TextChunker()

    chunks = chunker.chunk_text(text, max_tokens=20)

    assert chunks == [text]

# tests if the creation of multiple chunks works
@pytest.mark.parametrize("text, max_tokens", [
    ("I have the high ground!", 3),
    ("Thats what I do: I drink and I know things.", 5),
    ("Master Skywalker, there are too many of them! What are we going to do?", 7),
    ("Hello there.", 1)
])
def test_chunk_text_multiple_chunks(text, max_tokens):
    chunker = TextChunker()

    chunks = chunker.chunk_text(text, max_tokens)

    assert len(chunks) > 1


# tests if the chunker preserves the words of the text and their order
@pytest.mark.parametrize("text, max_tokens", [
    ("I have the high ground!", 3),
    ("When you play the Game of Thrones you win or you die.", 5),
    ("Never forget what you are, the rest of the world will not. Wear it like armor, and it can never be used to hurt you.", 2),
    ("Only a sith deals in absolutes.", 4)
])
def test_chunk_text_preserves_all_words(text, max_tokens):
    chunker = TextChunker()

    chunks = chunker.chunk_text(text, max_tokens)

    reconstructed = " ".join(chunks)

    assert reconstructed.split() == text.split()

# tests if a chunk exceeds the max tokens
@pytest.mark.parametrize("text, max_tokens", [
    ("I have the high ground!", 3),
    ("When you play the Game of Thrones you win or you die.", 5),
    ("Never forget what you are, the rest of the world will not. Wear it like armor, and it can never be used to hurt you.", 2),
    ("Only a sith deals in absolutes.", 4)
])
def test_chunk_text_respects_max_tokens(text, max_tokens):
    chunker = TextChunker()

    chunks = chunker.chunk_text(text, max_tokens=max_tokens)

    for chunk in chunks:
        assert chunker.estimate_token_count(chunk) < max_tokens

# tests that there are no empty chunks for a non-empty text
@pytest.mark.parametrize("text, max_tokens", [
    ("I have the high ground!", 3),
    ("When you play the Game of Thrones you win or you die.", 5),
    ("Valyria", 1),
    ("Only a sith deals in absolutes.", 4)
])
def test_chunk_text_no_empty_chunks(text, max_tokens):
    chunker = TextChunker()

    chunks = chunker.chunk_text(text, max_tokens)

    assert all(chunk.strip() != "" for chunk in chunks)

# tests if a single word is chunked correctly -- testing long words aswell as short
@pytest.mark.parametrize("text", [
    "Dog",
    "Eierschalensollbruchstellenverursacher",
    "Valyria",
    "Winterfell"
    "Hi"
])
def test_single_word_chunking(text):
    chunker = TextChunker()

    chunks = chunker.chunk_text(text, max_tokens=1)

    assert chunks == [text]
