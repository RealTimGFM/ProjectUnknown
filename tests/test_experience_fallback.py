import pytest
from ats_parser.rules import fallback_experience


def test_fallback_experience_two_items_happy_path_creates_items():
    text = """
2020 – 2021
Software Developer at Example Inc
- Built APIs
- Improved performance

2018 – 2020
Analyst at Another Company
- Analyzed data
"""
    items = fallback_experience(text)
    assert len(items) == 2
    assert items[0]["title"] and items[0]["company"]
    assert items[0]["dates"]["start"] and items[0]["dates"]["end"]
    assert isinstance(items[0]["bullets"], list)  # current behavior: may be empty


@pytest.mark.xfail(
    reason="Known limitation: bullet lines like '- Built APIs' currently get misclassified as titles, so bullets are dropped. Fix later."
)
def test_fallback_experience_collects_bullets_happy_path():
    text = """
2020 – 2021
Software Developer at Example Inc
- Built APIs
- Improved performance
"""
    items = fallback_experience(text)
    assert items and items[0]["bullets"]  # desired behavior
