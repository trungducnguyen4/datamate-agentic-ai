import pytest
from datamate.temporal.resolver import TemporalResolver


def test_resolve_contest_example_tuan_roi():
    # 2026-03-04 is Wednesday
    # Current week Monday: 2026-03-02
    # Previous week: 2026-02-23 to 2026-03-01
    q = "sp bán dc nhiều nhất tuần rồi là gì"
    res = TemporalResolver.resolve(q, "2026-03-04")
    assert res is not None
    assert res.start_date == "2026-02-23"
    assert res.end_date == "2026-03-01"


def test_resolve_thang_nay():
    q = "doanh thu tháng này là bao nhiêu"
    res = TemporalResolver.resolve(q, "2026-03-04")
    assert res is not None
    assert res.start_date == "2026-03-01"
    # Rulebook Rule 33: "Tháng này" calculates from 1st of month up to as_of_date (today)
    assert res.end_date == "2026-03-04"
    assert res.target_month == "2026-03"


def test_resolve_thang_truoc():
    # Previous month of March 2026 is Feb 2026 (28 days)
    q = "tháng trước bán được bao nhiêu đơn"
    res = TemporalResolver.resolve(q, "2026-03-04")
    assert res is not None
    assert res.start_date == "2026-02-01"
    assert res.end_date == "2026-02-28"
    assert res.target_month == "2026-02"


def test_resolve_lunar_festival():
    q = "doanh số dịp tết nguyên đán là bao nhiêu"
    res = TemporalResolver.resolve(q, "2026-03-04")
    assert res is not None
    # 2026 Lunar New Year Solar Date: 2026-02-17
    assert res.start_date == "2026-02-17"
    assert res.end_date == "2026-02-17"
    assert res.is_exact_day is True
