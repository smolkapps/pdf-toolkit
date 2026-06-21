"""Tests for `merge`: page-count is the sum and page order is preserved."""

from __future__ import annotations

import pytest
from pypdf import PdfReader

from pdftoolkit.core import PdfToolkitError, merge


def test_merge_page_count_is_sum(make_pdf, tmp_path):
    a = make_pdf("a.pdf", 2)
    b = make_pdf("b.pdf", 3)
    c = make_pdf("c.pdf", 1)
    out = str(tmp_path / "merged.pdf")

    total = merge([a, b, c], out)

    assert total == 6
    assert len(PdfReader(out).pages) == 6


def test_merge_preserves_order(make_pdf, tmp_path, page_markers):
    # Two docs, each with its own marker prefix so we can trace provenance.
    a = make_pdf("a.pdf", 2, label_prefix="PAGE")
    b = make_pdf("b.pdf", 2, label_prefix="DOC")
    out = str(tmp_path / "merged.pdf")

    merge([a, b], out)

    # First two pages come from A (PAGE 1, PAGE 2), then B's (DOC 1, DOC 2).
    assert page_markers(out, prefix="PAGE") == [1, 2, None, None]
    assert page_markers(out, prefix="DOC") == [None, None, 1, 2]


def test_merge_single_file(make_pdf, tmp_path):
    a = make_pdf("a.pdf", 4)
    out = str(tmp_path / "merged.pdf")
    assert merge([a], out) == 4
    assert len(PdfReader(out).pages) == 4


def test_merge_no_inputs_errors(tmp_path):
    with pytest.raises(PdfToolkitError):
        merge([], str(tmp_path / "out.pdf"))


def test_merge_missing_input_errors(make_pdf, tmp_path):
    a = make_pdf("a.pdf", 1)
    with pytest.raises(PdfToolkitError, match="not found"):
        merge([a, str(tmp_path / "does_not_exist.pdf")], str(tmp_path / "o.pdf"))


def test_merge_creates_valid_pdf(make_pdf, tmp_path):
    a = make_pdf("a.pdf", 1)
    out = str(tmp_path / "merged.pdf")
    merge([a, a], out)
    with open(out, "rb") as fh:
        assert fh.read(5) == b"%PDF-"
