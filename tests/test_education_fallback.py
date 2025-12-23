from ats_parser.rules import fallback_education


def test_fallback_education_merges_degree_and_school_lines():
    lines = [
        "Diploma of College Studies DEC – Computer Science",
        "LaSalle College, Montreal, QC",
        "2022 – 2024",
    ]
    out = fallback_education(lines)
    assert len(out) == 1
    assert "Diploma" in (out[0]["degree"] or "")
    assert "LaSalle" in (out[0]["school"] or "")
    assert out[0]["dates"]["start"]


def test_fallback_education_empty_is_safe():
    assert fallback_education([]) == []
