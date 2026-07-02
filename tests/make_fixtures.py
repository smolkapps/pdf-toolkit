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

import os
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


def make_image_pdf(
    path: str,
    image_pages: Iterable[int],
    *,
    total_pages: Optional[int] = None,
    size=(32, 24),
    pagesize=LETTER,
) -> str:
    """Create a PDF that embeds a distinct raster image on selected pages.

    Each page listed in ``image_pages`` (1-based) gets a small, deterministic
    RGB gradient image drawn on it; every page also carries the usual
    ``PAGE n`` text marker. Pages not listed contain only text. This gives the
    ``extract-images`` tests a document with a known number of embedded
    raster images at known page positions.

    Args:
        path: output file path.
        image_pages: 1-based page numbers that should carry an image.
        total_pages: total page count (defaults to max(image_pages)).
        size: (width, height) in pixels of each embedded image.
        pagesize: a reportlab pagesize tuple.

    Returns:
        ``path``.
    """
    from reportlab.lib.utils import ImageReader  # local: only image fixtures need it
    from PIL import Image

    image_pages = set(image_pages)
    if not image_pages:
        raise ValueError("image_pages must be non-empty")
    total = total_pages if total_pages is not None else max(image_pages)
    if total < max(image_pages):
        raise ValueError("total_pages is smaller than the highest image page")

    width_px, height_px = size
    pdf = canvas.Canvas(path, pagesize=pagesize)
    _, height = pagesize
    for n in range(1, total + 1):
        pdf.setFont("Helvetica-Bold", 48)
        pdf.drawString(72, height - 120, f"PAGE {n}")
        if n in image_pages:
            # A per-page-distinct gradient so each image is byte-different.
            img = Image.new("RGB", (width_px, height_px))
            for x in range(width_px):
                for y in range(height_px):
                    img.putpixel((x, y), ((x * 7 + n * 13) % 256, (y * 11) % 256, n * 5 % 256))
            pdf.drawImage(
                ImageReader(img), 72, height - 320, width=128, height=96
            )
        pdf.showPage()
    pdf.save()
    return path


def make_jpeg_image_pdf(
    path: str,
    *,
    size=(48, 32),
    pagesize=LETTER,
) -> str:
    """Create a single-page PDF embedding one DCT (JPEG) encoded image.

    Passing an on-disk ``.jpg`` to reportlab's ``drawImage`` preserves the
    JPEG bytes as a ``/DCTDecode`` image XObject (rather than re-encoding to
    Flate), giving the ``extract-images`` tests a non-Flate fixture whose
    extracted file should come back out as ``.jpg``.

    Returns:
        ``path``.
    """
    import tempfile

    from PIL import Image

    width_px, height_px = size
    img = Image.new("RGB", (width_px, height_px))
    for x in range(width_px):
        for y in range(height_px):
            img.putpixel((x, y), ((x * 5) % 256, (y * 7) % 256, 64))

    # reportlab reads the JPEG from a path, so stage it in a temp file.
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as handle:
        jpeg_path = handle.name
    try:
        img.save(jpeg_path, "JPEG", quality=85)
        pdf = canvas.Canvas(path, pagesize=pagesize)
        _, height = pagesize
        pdf.setFont("Helvetica-Bold", 48)
        pdf.drawString(72, height - 120, "PAGE 1")
        pdf.drawImage(jpeg_path, 72, height - 320, width=144, height=96)
        pdf.showPage()
        pdf.save()
    finally:
        os.remove(jpeg_path)
    return path


def make_shared_image_pdf(
    path: str,
    *,
    num_pages: int = 2,
    size=(16, 12),
    pagesize=LETTER,
) -> str:
    """Create a PDF where ONE image XObject is shared across several pages.

    Built directly with pikepdf: a single image stream is made an indirect
    object and referenced from every page's ``/Resources /XObject``. Because
    each page points at the *same* object, ``extract-images`` must de-duplicate
    them and produce exactly one file — this is the real de-duplication
    fixture (reportlab embeds a distinct copy per page and cannot exercise it).

    Returns:
        ``path``.
    """
    import zlib

    import pikepdf
    from pikepdf import Array, Dictionary, Name

    if num_pages < 1:
        raise ValueError("num_pages must be >= 1")

    width_px, height_px = size
    raw = bytearray()
    for y in range(height_px):
        for x in range(width_px):
            raw += bytes(((x * 7) % 256, (y * 11) % 256, 128))

    pdf = pikepdf.Pdf.new()
    image = pdf.make_stream(zlib.compress(bytes(raw)))
    image.stream_dict = Dictionary(
        Type=Name.XObject,
        Subtype=Name.Image,
        Width=width_px,
        Height=height_px,
        ColorSpace=Name.DeviceRGB,
        BitsPerComponent=8,
        Filter=Name.FlateDecode,
    )
    image_ref = pdf.make_indirect(image)

    content = b"q 100 0 0 75 100 500 cm /Im0 Do Q"
    _, page_h = pagesize
    for _ in range(num_pages):
        page = Dictionary(
            Type=Name.Page,
            MediaBox=Array([0, 0, pagesize[0], page_h]),
            Resources=Dictionary(XObject=Dictionary(Im0=image_ref)),
            Contents=pdf.make_stream(content),
        )
        pdf.pages.append(pikepdf.Page(pdf.make_indirect(page)))
    pdf.save(path)
    return path


def make_inline_image_pdf(
    path: str,
    *,
    size=(4, 4),
    pagesize=LETTER,
) -> str:
    """Create a single-page PDF whose only image is an inline (BI/ID/EI) image.

    Inline images live in the content stream rather than as XObjects, so they
    are invisible to a naive resource scan; this fixture verifies that
    ``extract-images`` promotes them (via ``externalize_inline_images``) and
    still exports them.

    Returns:
        ``path``.
    """
    import pikepdf
    from pikepdf import Array, Dictionary, Name

    width_px, height_px = size
    data = bytes((i * 5) % 256 for i in range(width_px * height_px * 3))
    content = (
        b"q 100 0 0 100 100 500 cm BI /W "
        + str(width_px).encode()
        + b" /H "
        + str(height_px).encode()
        + b" /CS /RGB /BPC 8 ID "
        + data
        + b" EI Q"
    )
    pdf = pikepdf.Pdf.new()
    page = Dictionary(
        Type=Name.Page,
        MediaBox=Array([0, 0, pagesize[0], pagesize[1]]),
        Resources=Dictionary(),
        Contents=pdf.make_stream(content),
    )
    pdf.pages.append(pikepdf.Page(pdf.make_indirect(page)))
    pdf.save(path)
    return path


def make_mixed_good_bad_image_pdf(
    path: str,
    *,
    size=(10, 8),
    pagesize=LETTER,
) -> str:
    """Create a 2-page PDF: one decodable image, one undecodable image.

    The bad image declares ``/FlateDecode`` but stores bytes that are not valid
    deflate data, so every decode path (qpdf and the Pillow fallback) fails on
    it. This is the shape ``extract-images`` must survive: the good image is
    exported, the bad one is skipped and counted — the run never aborts.

    Returns:
        ``path``.
    """
    import zlib

    import pikepdf
    from pikepdf import Array, Dictionary, Name

    width_px, height_px = size

    def _image_dict(stream):
        stream.stream_dict = Dictionary(
            Type=Name.XObject,
            Subtype=Name.Image,
            Width=width_px,
            Height=height_px,
            ColorSpace=Name.DeviceRGB,
            BitsPerComponent=8,
            Filter=Name.FlateDecode,
        )
        return stream

    pdf = pikepdf.Pdf.new()

    raw = bytearray()
    for y in range(height_px):
        for x in range(width_px):
            raw += bytes(((x * 9) % 256, (y * 3) % 256, 200))
    good = pdf.make_indirect(_image_dict(pdf.make_stream(zlib.compress(bytes(raw)))))
    bad = pdf.make_indirect(
        _image_dict(pdf.make_stream(b"this is not valid deflate data at all!!!"))
    )

    for ref in (good, bad):
        page = Dictionary(
            Type=Name.Page,
            MediaBox=Array([0, 0, pagesize[0], pagesize[1]]),
            Resources=Dictionary(XObject=Dictionary(Im0=ref)),
            Contents=pdf.make_stream(b"q 10 0 0 8 100 500 cm /Im0 Do Q"),
        )
        pdf.pages.append(pikepdf.Page(pdf.make_indirect(page)))
    pdf.save(path)
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
