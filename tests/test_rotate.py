"""Tests for `rotate`: the /Rotate key is set correctly on target pages."""

from __future__ import annotations

import pytest
from pypdf import PdfReader

from pdftoolkit.core import PdfToolkitError, rotate


def _rotations(path):
    """Return the effective /Rotate value (default 0) for each page."""
    reader = PdfReader(path)
    return [int(page.get("/Rotate", 0)) for page in reader.pages]


def test_rotate_selected_pages_sets_rotate(make_pdf, tmp_path):
    src = make_pdf("doc.pdf", 3)
    out = str(tmp_path / "rot.pdf")

    count = rotate(src, out, pages="1,2", degrees=90)

    assert count == 2
    # Pages 1 and 2 rotated to 90; page 3 untouched (0).
    assert _rotations(out) == [90, 90, 0]


def test_rotate_all_pages_default(make_pdf, tmp_path):
    src = make_pdf("doc.pdf", 2)
    out = str(tmp_path / "rot.pdf")
    count = rotate(src, out, pages=None, degrees=180)
    assert count == 2
    assert _rotations(out) == [180, 180]


def test_rotate_negative(make_pdf, tmp_path):
    src = make_pdf("doc.pdf", 1)
    out = str(tmp_path / "rot.pdf")
    rotate(src, out, pages="1", degrees=-90)
    # pypdf stores -90 literally (it does not normalise the sign); -90 and 270
    # are the same physical quarter-turn, so assert on the modular equivalence.
    assert _rotations(out)[0] % 360 == 270


def test_rotate_rejects_non_multiple_of_90(make_pdf, tmp_path):
    src = make_pdf("doc.pdf", 1)
    with pytest.raises(PdfToolkitError, match="multiple of 90"):
        rotate(src, str(tmp_path / "out.pdf"), pages="1", degrees=45)


def test_rotate_preserves_page_count(make_pdf, tmp_path):
    src = make_pdf("doc.pdf", 4)
    out = str(tmp_path / "rot.pdf")
    rotate(src, out, pages="2", degrees=90)
    assert len(PdfReader(out).pages) == 4
