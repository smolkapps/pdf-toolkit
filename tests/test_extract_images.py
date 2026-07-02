"""Tests for the ``extract-images`` command.

Fixtures are synthetic PDFs built by reportlab with small, deterministic
raster images embedded on known pages (see ``make_fixtures.make_image_pdf``),
so we can assert on the number, page positions, and decodability of the images
that come back out — no binary fixtures are checked in.
"""

from __future__ import annotations

import os

from PIL import Image

from pdftoolkit.cli import main
from pdftoolkit.core import PdfToolkitError, extract_images


def _list_pngs(outdir):
    return sorted(f for f in os.listdir(outdir) if f.lower().endswith(".png"))


def test_extracts_one_image_per_image_page(make_image_pdf, tmp_path):
    src = make_image_pdf("doc.pdf", [1, 3], total_pages=4)
    outdir = str(tmp_path / "imgs")

    result = extract_images(src, outdir)

    assert len(result) == 2
    assert result.skipped == 0
    # File names encode the 1-based page each image was first seen on.
    names = sorted(os.path.basename(p) for p in result.files)
    assert names[0].startswith("doc_p001_img")
    assert names[1].startswith("doc_p003_img")


def test_extracted_files_are_valid_decodable_images(make_image_pdf, tmp_path):
    src = make_image_pdf("doc.pdf", [1], size=(40, 20))
    outdir = str(tmp_path / "imgs")

    result = extract_images(src, outdir)

    assert len(result) == 1
    path = result.files[0]
    assert os.path.getsize(path) > 0
    with Image.open(path) as img:
        # The embedded image survives round-trip at its original pixel size.
        assert img.size == (40, 20)


def test_undecodable_image_is_skipped_not_fatal(
    make_mixed_good_bad_image_pdf, tmp_path
):
    # One decodable image and one image whose stream cannot be inflated. The
    # bad image must be skipped and counted, the good one still exported, and
    # the call must not raise — the whole point of the broadened error handling.
    src = make_mixed_good_bad_image_pdf("mixed.pdf", size=(10, 8))
    outdir = str(tmp_path / "imgs")

    result = extract_images(src, outdir)

    assert len(result) == 1
    assert result.skipped == 1
    # No orphaned/partial file was left behind for the failed image.
    assert len(_list_pngs(outdir)) + len(
        [f for f in os.listdir(outdir) if f.lower().endswith(".jpg")]
    ) == 1
    with Image.open(result.files[0]) as img:
        assert img.size == (10, 8)


def test_cli_reports_skipped_images(make_mixed_good_bad_image_pdf, tmp_path, capsys):
    src = make_mixed_good_bad_image_pdf("mixed.pdf")
    outdir = str(tmp_path / "out")

    rc = main(["extract-images", src, "--outdir", outdir])

    assert rc == 0
    out = capsys.readouterr().out
    assert "Extracted 1 image(s)" in out
    assert "skipped 1 image(s)" in out


def test_no_images_returns_empty_result(make_pdf, tmp_path):
    src = make_pdf("text_only.pdf", 3)  # text fixture has no raster images
    outdir = str(tmp_path / "imgs")

    result = extract_images(src, outdir)

    assert len(result) == 0
    assert result.files == []


def test_distinct_images_each_extracted(make_image_pdf, tmp_path):
    # Two pages carrying per-page-distinct images: no de-duplication, 2 files.
    src = make_image_pdf("doc.pdf", [1, 2])
    outdir = str(tmp_path / "imgs")

    result = extract_images(src, outdir)

    assert len(result) == 2


def test_shared_image_extracted_once(make_shared_image_pdf, tmp_path):
    # A single image XObject is referenced from three pages' /Resources. It is
    # the *same* object, so de-duplication must yield exactly one file named
    # for the first page it appears on.
    src = make_shared_image_pdf("shared.pdf", num_pages=3, size=(16, 12))
    outdir = str(tmp_path / "imgs")

    result = extract_images(src, outdir)

    assert len(result) == 1
    assert result.skipped == 0
    assert os.path.basename(result.files[0]).startswith("shared_p001_img")
    with Image.open(result.files[0]) as img:
        assert img.size == (16, 12)


def test_jpeg_image_extracted_as_jpg(make_jpeg_image_pdf, tmp_path):
    # A DCT/JPEG-encoded image should come back out as .jpg (qpdf's fast path
    # preserves the stored encoding) and decode at its original dimensions.
    src = make_jpeg_image_pdf("photo.pdf", size=(48, 32))
    outdir = str(tmp_path / "imgs")

    result = extract_images(src, outdir)

    assert len(result) == 1
    path = result.files[0]
    assert path.lower().endswith(".jpg")
    with Image.open(path) as img:
        assert img.format == "JPEG"
        assert img.size == (48, 32)


def test_inline_image_is_extracted(make_inline_image_pdf, tmp_path):
    # Inline BI/ID/EI images live in the content stream, not /Resources. They
    # must be promoted to XObjects and exported, not silently dropped.
    src = make_inline_image_pdf("inline.pdf", size=(4, 4))
    outdir = str(tmp_path / "imgs")

    result = extract_images(src, outdir)

    assert len(result) == 1
    assert result.skipped == 0
    with Image.open(result.files[0]) as img:
        assert img.size == (4, 4)


def test_min_size_filters_small_images(make_image_pdf, tmp_path):
    src = make_image_pdf("doc.pdf", [1], size=(10, 10))
    outdir = str(tmp_path / "imgs")

    kept = extract_images(src, outdir, min_size=8)
    assert len(kept) == 1

    outdir2 = str(tmp_path / "imgs2")
    dropped = extract_images(src, outdir2, min_size=32)
    assert len(dropped) == 0


def test_negative_min_size_rejected(make_image_pdf, tmp_path):
    src = make_image_pdf("doc.pdf", [1])
    try:
        extract_images(src, str(tmp_path / "imgs"), min_size=-1)
    except PdfToolkitError as exc:
        assert "min-size" in str(exc)
    else:  # pragma: no cover - guard against silent acceptance
        raise AssertionError("expected PdfToolkitError for negative min_size")


def test_missing_input_raises(tmp_path):
    try:
        extract_images(str(tmp_path / "nope.pdf"), str(tmp_path / "imgs"))
    except PdfToolkitError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected PdfToolkitError for missing input")


# --------------------------------------------------------------------------- #
# CLI-level tests
# --------------------------------------------------------------------------- #
def test_cli_extract_images(make_image_pdf, tmp_path, capsys):
    src = make_image_pdf("doc.pdf", [1, 2])
    outdir = str(tmp_path / "out")

    rc = main(["extract-images", src, "--outdir", outdir])

    assert rc == 0
    out = capsys.readouterr().out
    assert "Extracted 2 image(s)" in out
    assert len(_list_pngs(outdir)) == 2


def test_cli_extract_images_none_found(make_pdf, tmp_path, capsys):
    src = make_pdf("text_only.pdf", 2)
    outdir = str(tmp_path / "out")

    rc = main(["extract-images", src, "--outdir", outdir])

    assert rc == 0
    assert "No embedded images found" in capsys.readouterr().out


def test_cli_extract_images_min_size(make_image_pdf, tmp_path, capsys):
    src = make_image_pdf("doc.pdf", [1], size=(10, 10))
    outdir = str(tmp_path / "out")

    rc = main(["extract-images", src, "--outdir", outdir, "--min-size", "50"])

    assert rc == 0
    assert "No embedded images found" in capsys.readouterr().out
