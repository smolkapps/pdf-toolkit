"""Tests for the page-selector parser (`pdftoolkit.ranges`)."""

from __future__ import annotations

import pytest

from pdftoolkit.ranges import RangeError, parse_pages


def test_single_page():
    assert parse_pages("3", 5) == [2]


def test_simple_range():
    assert parse_pages("2-4", 5) == [1, 2, 3]


def test_comma_list():
    assert parse_pages("1,3,5", 5) == [0, 2, 4]


def test_combination():
    assert parse_pages("1-3,5,7-8", 8) == [0, 1, 2, 4, 6, 7]


def test_whitespace_tolerated():
    assert parse_pages(" 1 - 3 , 5 ", 5) == [0, 1, 2, 4]


def test_descending_range_expands_reverse():
    assert parse_pages("4-2", 5) == [3, 2, 1]


def test_single_page_range():
    assert parse_pages("3-3", 5) == [2]


def test_duplicates_preserved():
    assert parse_pages("1,1,2", 3) == [0, 0, 1]


@pytest.mark.parametrize("bad", ["", "   ", ",", "1,,2", "abc", "1-", "-3", "1-2-3"])
def test_malformed_raises(bad):
    with pytest.raises(RangeError):
        parse_pages(bad, 5)


def test_zero_page_rejected():
    with pytest.raises(RangeError):
        parse_pages("0", 5)


def test_out_of_range_rejected():
    with pytest.raises(RangeError, match="out of range"):
        parse_pages("6", 5)


def test_out_of_range_in_span_rejected():
    with pytest.raises(RangeError):
        parse_pages("3-9", 5)
