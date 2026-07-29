from app.core.text import chunk_text, normalize_name


def test_chunk_boundary_and_overlap() -> None:
    chunks = chunk_text("a" * 24_001)
    assert len(chunks) == 2
    assert chunks[0][1] == 24_000
    assert chunks[1][0] == 23_500


def test_normalized_name_merges_spacing_and_case() -> None:
    assert normalize_name("Open AI") == normalize_name("open-ai")
