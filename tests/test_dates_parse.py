import pytest
from ats_parser.rules import parse_date_range


@pytest.mark.parametrize(
    "s, exp_start, exp_end",
    [
        ("2008 – Present", "2008-01", "Present"),
        ("2006 – 2007", "2006-01", "2007-01"),
        ("Jun 2006 – Sep 2006", "2006-06", "2006-09"),
        ("06/2006 – 09/2006", "2006-06", "2006-09"),
        ("June – Sept 2006", "2006-06", "2006-09"),  # borrow year
    ],
)
def test_parse_date_range_common_cases(s, exp_start, exp_end):
    start, end, months = parse_date_range(s)
    assert start == exp_start
    assert end == exp_end
    # months may be None depending on bad input; for these it should be computed except Present
    if exp_end != "Present":
        assert isinstance(months, int) and months >= 1


def test_parse_date_range_garbage_is_safe():
    start, end, months = parse_date_range("SomeTime – Whenever")
    assert start is None and end is None and months is None
