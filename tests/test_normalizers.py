"""Adversarial + correctness tests for normalizers."""

from __future__ import annotations

from datetime import date

import pytest

from submission_harness.verify.normalizers import (
    AmbiguousDateError,
    missing_to_none,
    normalize_amount,
    normalize_code,
    normalize_date,
    normalize_int,
    split_compound_limits,
    token_overlap,
)


def test_null_vs_empty_string():
    assert missing_to_none(None) is None
    assert missing_to_none("") is None
    assert missing_to_none("   ") is None
    assert missing_to_none("x") == "x"


def test_amount_1m_vs_million():
    assert normalize_amount("1M") == 1_000_000.0
    assert normalize_amount("1m") == 1_000_000.0
    assert normalize_amount("$1,000,000") == 1_000_000.0
    assert normalize_amount("1000000") == 1_000_000.0
    assert normalize_amount(1_000_000) == 1_000_000.0
    assert normalize_amount("1.5M") == 1_500_000.0
    assert normalize_amount("$2,500") == 2_500.0


def test_compound_limits_rejected_as_single_amount():
    assert normalize_amount("1M/2M") is None
    assert split_compound_limits("1M/2M") == (1_000_000.0, 2_000_000.0)


def test_date_iso_and_us():
    assert normalize_date(date(2026, 12, 18)) == "2026-12-18"
    assert normalize_date("2026-12-18") == "2026-12-18"
    assert normalize_date("12/18/2026") == "2026-12-18"


def test_date_format_collision_ambiguous():
    # 05/06/2024 could be May 6 or June 5
    with pytest.raises(AmbiguousDateError):
        normalize_date("05/06/2024")


def test_date_unambiguous_day_gt_12():
    assert normalize_date("15/03/2024") == "2024-03-15"  # day-first only
    assert normalize_date("03/15/2024") == "2024-03-15"  # month-first only


def test_code_strips_non_digits():
    assert normalize_code("NAICS 493110") == "493110"
    assert normalize_code("42-13") == "4213"


def test_year_built():
    assert normalize_int("1984") == 1984
    assert normalize_int(1984.0) == 1984


def test_token_overlap_tolerant():
    assert token_overlap("Summit Logistics LLC", "summit logistics llc") == 1.0
    assert token_overlap(None, None) == 1.0
    assert token_overlap("abc", None) == 0.0
    assert token_overlap(
        "Long-haul trucking and freight brokerage",
        "long haul trucking freight brokerage",
    ) >= 0.8
