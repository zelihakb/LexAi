
from app.services.helpers import (
    normalize_text,
    extract_query_terms,
    parse_json_block,
    minmax_normalize,
    smart_join_parts,
)


def test_normalize_turkish_text():
    result = normalize_text("  İDARİ, Para Cezası! ")
    assert result == "idari para cezası"


def test_extract_query_terms():
    result = extract_query_terms(
        "İdari para cezası ve ödeme emri"
    )
    assert result == [
        "idari", "para", "cezası", "ödeme", "emri"
    ]


def test_parse_gemini_json():
    raw = '```json\n{"relation": "procedural",}\n```'
    result = parse_json_block(raw)
    assert result == {"relation": "procedural"}


def test_score_normalization():
    result = minmax_normalize([10, 20, 30])
    assert result == [0.0, 0.5, 1.0]


def test_merge_overlapping_text():
    parts = [
        "idari para cezası",
        "cezası kesinleşmeden",
        "kesinleşmeden ödeme emri",
    ]
    result = smart_join_parts(parts)

    assert result == (
        "idari para cezası kesinleşmeden ödeme emri"
    )
