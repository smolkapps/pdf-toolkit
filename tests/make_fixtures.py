"""Build deterministic, known-content PDF fixtures with reportlab.

The key property every fixture provides: each page carries a *detectable*
text marker of the form ``PAGE 1``, ``PAGE 2``, ... so tests can verify page
order and identity after merge/split/extract/delete/reorder by reading the
extracted text back out with pypdf.

These helpers are imported by the test suite (via a pytest fixture) and can
also be run as a script to drop a sample file on disk for manual play:

    python tests/make_fixtures.py /tmp/sample.pdf 5
"""

from __future__ import annotations

import sys
from typing import Iterable, Optional

from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas


def make_pdf(
    path: str,
    num_pages: int,
    *,
    label_prefix: str = "PAGE",
    pagesize=LETTER,
    extra_filler: bool = False,
) -> str:
    """Create a PDF at ``path`` with ``num_pages`` pages.

    Each page n (1-based) renders the string ``"{label_prefix} {n}"`` (e.g.
    "PAGE 1") in large type near the top, plus a smaller unique tag. The text
    is real, selectable text (not an image), so pypdf can extract it.

    Args:
        path: output file path.
        num_pages: number of pages to draw (must be >= 1).
        label_prefix: marker prefix; vary it to make distinguishable docs.
        pagesize: a reportlab pagesize tuple (default LETTER, 612x792 pt).
        extra_filler: if True, draw many lines of filler text per page so the
            content stream is large enough to make compression measurable.

    Returns:
        ``path`` (for convenient chaining).
    """
    if num_pages < 1:
        raise ValueError("num_pages must be >= 1")

    pdf = canvas.Canvas(path, pagesize=pagesize)
    width, height = pagesize
    for n in range(1, num_pages + 1):
        marker = f"{label_prefix} {n}"
        pdf.setFont("Helvetica-Bold", 48)
        pdf.drawString(72, height - 120, marker)
        pdf.setFont("Helvetica", 14)
        pdf.drawString(72, height - 160, f"This is page {n} of {num_pages}.")
        pdf.drawString(72, height - 180, f"marker-token-{label_prefix.lower()}-{n}")
        if extra_filler:
            # Lots of distinct, compressible text to give `compress` something
            # real to chew on for the compression test.
            pdf.setFont("Helvetica", 10)
            y = height - 220
            for line in range(60):
                pdf.drawString(
                    72,
                    y,
                    f"Filler line {line:03d} on page {n}: "
                    + "lorem ipsum dolor sit amet " * 3,
                )
                y -= 12
                if y < 72:
                    break
        pdf.showPage()
    pdf.save()
    return path


def make_named_pages(path: str, labels: Iterable[str], *, pagesize=LETTER) -> str:
    """Create a PDF where each page shows an explicit label from ``labels``.

    Useful when a test needs specific, non-sequential markers.

    Returns:
        ``path``.
    """
    labels = list(labels)
    if not labels:
        raise ValueError("labels must be non-empty")
    pdf = canvas.Canvas(path, pagesize=pagesize)
    _, height = pagesize
    for label in labels:
        pdf.setFont("Helvetica-Bold", 48)
        pdf.drawString(72, height - 120, label)
        pdf.showPage()
    pdf.save()
    return path


def _main(argv: Optional[list] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print("usage: make_fixtures.py <out.pdf> [num_pages=3]", file=sys.stderr)
        return 2
    out = argv[0]
    pages = int(argv[1]) if len(argv) > 1 else 3
    make_pdf(out, pages)
    print(f"wrote {out} ({pages} pages)")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
