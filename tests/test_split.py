"""Tests for `split`: ranges, --every chunking, and --all one-per-page."""

from __future__ import annotations

import os

import pytest
from pypdf import PdfReader

from pdftoolkit.core import PdfToolkitError, split


def test_split_ranges_counts_and_pages(make_pdf, tmp_path, page_markers):
    src = make_pdf("doc.pdf", 6)
    outdir = str(tmp_path / "out")

    result = split(src, outdir, ranges="1-3,5")

    assert len(result) == 1
    out = result.files[0]
    assert len(PdfReader(out).pages) == 4
    # Pages 1,2,3 then 5 (0-based 0,1,2,4) -> markers 1,2,3,5.
    assert page_markers(out) == [1, 2, 3, 5]


def test_split_every_n_chunks(make_pdf, tmp_path, page_markers):
    src = make_pdf("doc.pdf", 5)
    outdir = str(tmp_path / "out")

    result = split(src, outdir, every=2)

    # 5 pages in chunks of 2 -> [2, 2, 1] across 3 files.
    assert len(result) == 3
    counts = [len(PdfReader(f).pages) for f in result.files]
    assert counts == [2, 2, 1]
    # Content order across the chunk files must be contiguous 1..5.
    seen = []
    for f in result.files:
        seen.extend(page_markers(f))
    assert seen == [1, 2, 3, 4, 5]


def test_split_every_exact_multiple(make_pdf, tmp_path):
    src = make_pdf("doc.pdf", 4)
    result = split(src, str(tmp_path / "out"), every=2)
    assert len(result) == 2
    assert [len(PdfReader(f).pages) for f in result.files] == [2, 2]


def test_split_all_one_file_per_page(make_pdf, tmp_path, page_markers):
    src = make_pdf("doc.pdf", 3)
    outdir = str(tmp_path / "out")

    result = split(src, outdir, all_pages=True)

    assert len(result) == 3
    for i, f in enumerate(result.files, start=1):
        assert len(PdfReader(f).pages) == 1
        assert page_markers(f) == [i]


def test_split_files_are_written_to_outdir(make_pdf, tmp_path):
    src = make_pdf("doc.pdf", 2)
    outdir = str(tmp_path / "nested" / "out")  # does not exist yet
    result = split(src, outdir, all_pages=True)
    for f in result.files:
        assert os.path.exists(f)
        assert os.path.dirname(f) == outdir


def test_split_requires_exactly_one_mode(make_pdf, tmp_path):
    src = make_pdf("doc.pdf", 3)
    outdir = str(tmp_path / "out")
    # zero modes
    with pytest.raises(PdfToolkitError):
        split(src, outdir)
    # two modes
    with pytest.raises(PdfToolkitError):
        split(src, outdir, ranges="1", every=2)


def test_split_every_rejects_zero(make_pdf, tmp_path):
    src = make_pdf("doc.pdf", 3)
    with pytest.raises(PdfToolkitError):
        split(src, str(tmp_path / "out"), every=0)


def test_split_range_out_of_bounds_errors(make_pdf, tmp_path):
    src = make_pdf("doc.pdf", 3)
    with pytest.raises(PdfToolkitError, match="out of range"):
        split(src, str(tmp_path / "out"), ranges="1-9")
