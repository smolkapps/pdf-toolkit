"""Tests for extract / delete / reorder page operations.

These assert on *content order* (via per-page markers), not just page counts,
which is the only way to prove the right pages ended up in the right place.
"""

from __future__ import annotations

import pytest
from pypdf import PdfReader

from pdftoolkit.core import (
    PdfToolkitError,
    delete_pages,
    extract_pages,
    reorder,
)


def test_extract_subset_order(make_pdf, tmp_path, page_markers):
    src = make_pdf("doc.pdf", 5)
    out = str(tmp_path / "extract.pdf")

    count = extract_pages(src, out, pages="2-4")

    assert count == 3
    assert page_markers(out) == [2, 3, 4]


def test_extract_noncontiguous(make_pdf, tmp_path, page_markers):
    src = make_pdf("doc.pdf", 5)
    out = str(tmp_path / "extract.pdf")
    extract_pages(src, out, pages="1,3,5")
    assert page_markers(out) == [1, 3, 5]


def test_delete_removes_pages(make_pdf, tmp_path, page_markers):
    src = make_pdf("doc.pdf", 5)
    out = str(tmp_path / "deleted.pdf")

    remaining = delete_pages(src, out, pages="3")

    assert remaining == 4
    assert page_markers(out) == [1, 2, 4, 5]


def test_delete_multiple(make_pdf, tmp_path, page_markers):
    src = make_pdf("doc.pdf", 5)
    out = str(tmp_path / "deleted.pdf")
    delete_pages(src, out, pages="1,5")
    assert page_markers(out) == [2, 3, 4]


def test_delete_all_pages_refused(make_pdf, tmp_path):
    src = make_pdf("doc.pdf", 3)
    with pytest.raises(PdfToolkitError, match="every page"):
        delete_pages(src, str(tmp_path / "out.pdf"), pages="1-3")


def test_reorder_permutation(make_pdf, tmp_path, page_markers):
    src = make_pdf("doc.pdf", 3)
    out = str(tmp_path / "reordered.pdf")

    count = reorder(src, out, order="3,1,2")

    assert count == 3
    assert len(PdfReader(out).pages) == 3
    assert page_markers(out) == [3, 1, 2]


def test_reorder_reverse_via_descending_range(make_pdf, tmp_path, page_markers):
    src = make_pdf("doc.pdf", 4)
    out = str(tmp_path / "rev.pdf")
    reorder(src, out, order="4-1")
    assert page_markers(out) == [4, 3, 2, 1]


def test_reorder_with_duplicates(make_pdf, tmp_path, page_markers):
    src = make_pdf("doc.pdf", 3)
    out = str(tmp_path / "dup.pdf")
    reorder(src, out, order="1,1,2")
    assert page_markers(out) == [1, 1, 2]


def test_extract_bad_range_errors(make_pdf, tmp_path):
    src = make_pdf("doc.pdf", 3)
    with pytest.raises(PdfToolkitError):
        extract_pages(src, str(tmp_path / "out.pdf"), pages="0")
