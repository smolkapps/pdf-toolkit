"""Shared pytest fixtures: build known-content PDFs in a temp dir.

Helpers come from ``make_fixtures`` (sibling module). We add the tests dir to
``sys.path`` defensively so ``import make_fixtures`` works regardless of how
pytest is invoked.
"""

from __future__ import annotations

import os
import re
import sys

import pytest
from pypdf import PdfReader

sys.path.insert(0, os.path.dirname(__file__))

import make_fixtures  # noqa: E402


@pytest.fixture
def make_pdf(tmp_path):
    """Return a factory that writes a labelled PDF into the test's tmp_path.

    Usage:
        path = make_pdf("doc.pdf", 5)
        path = make_pdf("other.pdf", 3, label_prefix="DOC")
    """

    def _factory(name, num_pages, *, label_prefix="PAGE", extra_filler=False):
        out = str(tmp_path / name)
        return make_fixtures.make_pdf(
            out,
            num_pages,
            label_prefix=label_prefix,
            extra_filler=extra_filler,
        )

    return _factory


@pytest.fixture
def make_image_pdf(tmp_path):
    """Return a factory that writes a PDF with embedded images into tmp_path.

    Usage:
        path = make_image_pdf("doc.pdf", [1, 3])          # images on pages 1 & 3
        path = make_image_pdf("doc.pdf", [2], total_pages=4)
    """

    def _factory(name, image_pages, *, total_pages=None, size=(32, 24)):
        out = str(tmp_path / name)
        return make_fixtures.make_image_pdf(
            out, image_pages, total_pages=total_pages, size=size
        )

    return _factory


@pytest.fixture
def page_markers():
    """Return a helper that reads the per-page integer markers from a PDF.

    Given a PDF whose pages were created with label_prefix "PAGE", returns the
    list of integers in page order, e.g. [1, 2, 3]. This is how tests assert
    that page *content* (not just count) ended up in the expected order after
    an operation.
    """

    def _read(path, prefix="PAGE"):
        reader = PdfReader(path)
        markers = []
        pattern = re.compile(rf"{re.escape(prefix)}\s+(\d+)")
        for page in reader.pages:
            content = page.extract_text() or ""
            match = pattern.search(content)
            markers.append(int(match.group(1)) if match else None)
        return markers

    return _read
