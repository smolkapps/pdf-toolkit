"""Tests for `text`, `info`, and `compress`."""

from __future__ import annotations

import os

import pytest

from pdftoolkit.core import PdfToolkitError, compress, info, text


# --------------------------------------------------------------------------- #
# text
# --------------------------------------------------------------------------- #
def test_text_extracts_known_markers(make_pdf):
    src = make_pdf("doc.pdf", 3)
    pages = text(src)
    assert len(pages) == 3
    for i, page_text in enumerate(pages, start=1):
        assert f"PAGE {i}" in page_text
        assert f"This is page {i}" in page_text


def test_text_length_equals_page_count(make_pdf):
    src = make_pdf("doc.pdf", 7)
    assert len(text(src)) == 7


def test_text_missing_file_errors(tmp_path):
    with pytest.raises(PdfToolkitError, match="not found"):
        text(str(tmp_path / "nope.pdf"))


# --------------------------------------------------------------------------- #
# info
# --------------------------------------------------------------------------- #
def test_info_reports_page_count(make_pdf):
    src = make_pdf("doc.pdf", 5)
    result = info(src)
    assert result.pages == 5
    assert result.encrypted is False
    assert result.file_size > 0


def test_info_reports_letter_page_size(make_pdf):
    src = make_pdf("doc.pdf", 1)
    result = info(src)
    # reportlab LETTER is 612 x 792 points.
    assert result.page_sizes[0] == (612.0, 792.0)


def test_info_has_pdf_version(make_pdf):
    src = make_pdf("doc.pdf", 1)
    result = info(src)
    assert result.pdf_version is not None
    assert result.pdf_version.startswith("1.") or result.pdf_version.startswith("2.")


# --------------------------------------------------------------------------- #
# compress
# --------------------------------------------------------------------------- #
def test_compress_produces_valid_smaller_or_equal_pdf(make_pdf, tmp_path):
    # Heavy filler text gives qpdf real, compressible content.
    src = make_pdf("doc.pdf", 10, extra_filler=True)
    out = str(tmp_path / "small.pdf")

    result = compress(src, out)

    assert os.path.exists(out)
    # Output must be a valid PDF.
    with open(out, "rb") as fh:
        assert fh.read(5) == b"%PDF-"
    # Guarantee: never larger than the input.
    assert result.size_after <= result.size_before
    # Page count is preserved.
    assert info(out).pages == 10


def test_compress_never_grows_tiny_pdf(make_pdf, tmp_path):
    # A tiny PDF may not shrink; the contract is "<= original", enforced by
    # the fallback-to-copy path.
    src = make_pdf("tiny.pdf", 1)
    out = str(tmp_path / "tiny_out.pdf")
    result = compress(src, out)
    assert result.size_after <= result.size_before
    assert info(out).pages == 1


def test_compress_missing_file_errors(tmp_path):
    with pytest.raises(PdfToolkitError, match="not found"):
        compress(str(tmp_path / "nope.pdf"), str(tmp_path / "o.pdf"))
