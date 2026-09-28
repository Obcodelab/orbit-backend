from modules.ai.chunking import chunk_text


def test_chunk_text_empty_string_returns_no_chunks():
    assert chunk_text("") == []
    assert chunk_text("   ") == []


def test_chunk_text_shorter_than_chunk_size_returns_one_chunk():
    chunks = chunk_text("hello world", chunk_size=800, overlap=100)
    assert chunks == ["hello world"]


def test_chunk_text_splits_with_overlap():
    text = "a" * 1000
    chunks = chunk_text(text, chunk_size=800, overlap=100)

    assert len(chunks) == 2
    assert chunks[0] == "a" * 800
    assert chunks[1] == "a" * 300  # positions 700..999


def test_chunk_text_overlap_regions_actually_overlap():
    text = "0123456789" * 100
    chunks = chunk_text(text, chunk_size=800, overlap=100)

    assert chunks[0][-100:] == chunks[1][:100]
