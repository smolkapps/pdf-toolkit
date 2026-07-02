"""Core PDF operations for pdftoolkit.

This module is the library layer: every function here is pure-ish (it reads
input paths and writes output paths) and raises :class:`PdfToolkitError` for
any condition the user can cause (missing file, bad page selector, encrypted
input, etc.). The CLI is a thin wrapper that translates these into process
exit codes and stderr messages.

Backends:
    * ``pypdf`` for structural page operations (merge/split/rotate/extract/
      delete/reorder) and text extraction — its Python-native API keeps the
      page tree easy to manipulate.
    * ``pikepdf`` (libqpdf) for ``info`` (robust metadata + encryption probe)
      and ``compress`` (object streams + stream recompression), which qpdf
      does far better than pypdf.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

import pikepdf
import pikepdf.models.image as _image_module
from pypdf import PdfReader, PdfWriter

from .ranges import RangeError, parse_pages


class PdfToolkitError(Exception):
    """User-facing error: bad input, unreadable/encrypted file, etc.

    The CLI catches this and prints ``str(exc)`` to stderr, exiting non-zero.
    """


# --------------------------------------------------------------------------- #
# Internal helpers
# --------------------------------------------------------------------------- #
def _require_input(path: str) -> None:
    """Raise PdfToolkitError unless ``path`` is an existing, readable file."""
    if not os.path.exists(path):
        raise PdfToolkitError(f"input file not found: {path}")
    if not os.path.isfile(path):
        raise PdfToolkitError(f"not a file: {path}")
    if not os.access(path, os.R_OK):
        raise PdfToolkitError(f"input file not readable: {path}")


def _open_reader(path: str) -> PdfReader:
    """Open ``path`` as a PdfReader, mapping failures to PdfToolkitError.

    Encrypted files that need a password are rejected with a clear message
    rather than raising deep inside pypdf; files with an *empty* user
    password are transparently decrypted, matching common viewer behaviour.
    """
    _require_input(path)
    try:
        reader = PdfReader(path)
    except Exception as exc:  # pragma: no cover - depends on corrupt input
        raise PdfToolkitError(f"could not read PDF {path}: {exc}") from exc
    if reader.is_encrypted:
        try:
            # An empty password unlocks files encrypted only to deter copying.
            if reader.decrypt("") == 0:
                raise PdfToolkitError(
                    f"{path} is password-protected; decrypt it first "
                    f"(this toolkit does not accept passwords)"
                )
        except PdfToolkitError:
            raise
        except Exception as exc:
            raise PdfToolkitError(
                f"{path} is encrypted and could not be opened: {exc}"
            ) from exc
    return reader


def _ensure_parent_dir(path: str) -> None:
    """Create the parent directory of ``path`` if it does not yet exist."""
    parent = os.path.dirname(os.path.abspath(path))
    os.makedirs(parent, exist_ok=True)


def _write(writer: PdfWriter, out_path: str) -> None:
    """Write a PdfWriter to disk, creating parent dirs and mapping errors."""
    _ensure_parent_dir(out_path)
    try:
        with open(out_path, "wb") as handle:
            writer.write(handle)
    except OSError as exc:
        raise PdfToolkitError(f"could not write {out_path}: {exc}") from exc


def _select_indices(reader: PdfReader, selector: str) -> List[int]:
    """Parse ``selector`` against the reader's page count, mapping RangeError."""
    try:
        return parse_pages(selector, len(reader.pages))
    except RangeError as exc:
        raise PdfToolkitError(str(exc)) from exc


# --------------------------------------------------------------------------- #
# merge
# --------------------------------------------------------------------------- #
def merge(inputs: Sequence[str], out_path: str) -> int:
    """Concatenate ``inputs`` in order into a single PDF at ``out_path``.

    Returns:
        The total number of pages written.
    """
    if not inputs:
        raise PdfToolkitError("merge requires at least one input file")
    writer = PdfWriter()
    total = 0
    for path in inputs:
        reader = _open_reader(path)
        for page in reader.pages:
            writer.add_page(page)
            total += 1
    if total == 0:
        raise PdfToolkitError("merge produced no pages (all inputs were empty)")
    _write(writer, out_path)
    return total


# --------------------------------------------------------------------------- #
# split
# --------------------------------------------------------------------------- #
@dataclass
class SplitResult:
    """Outcome of a :func:`split` call."""

    files: List[str] = field(default_factory=list)

    def __len__(self) -> int:  # convenience for tests / callers
        return len(self.files)


def _write_subset(reader: PdfReader, indices: Sequence[int], out_path: str) -> None:
    """Write the given 0-based page ``indices`` of ``reader`` to ``out_path``."""
    writer = PdfWriter()
    for idx in indices:
        writer.add_page(reader.pages[idx])
    _write(writer, out_path)


def split(
    in_path: str,
    outdir: str,
    *,
    ranges: Optional[str] = None,
    every: Optional[int] = None,
    all_pages: bool = False,
) -> SplitResult:
    """Split ``in_path`` into multiple PDFs in ``outdir``.

    Exactly one mode must be selected:
        * ``ranges="1-3,5"`` -> a single output containing those pages.
        * ``every=N``        -> consecutive chunks of N pages each.
        * ``all_pages=True`` -> one output file per page.

    Output files are named ``<stem>_partNNN.pdf`` (ranges/every) or
    ``<stem>_pageNNN.pdf`` (all), zero-padded for stable sorting.

    Returns:
        A :class:`SplitResult` listing the created file paths in order.
    """
    modes = [ranges is not None, every is not None, all_pages]
    if sum(bool(m) for m in modes) != 1:
        raise PdfToolkitError(
            "split requires exactly one of --ranges, --every, or --all"
        )

    reader = _open_reader(in_path)
    page_count = len(reader.pages)
    if page_count == 0:
        raise PdfToolkitError(f"{in_path} has no pages to split")

    os.makedirs(outdir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(in_path))[0]
    result = SplitResult()

    if ranges is not None:
        indices = _select_indices(reader, ranges)
        out_path = os.path.join(outdir, f"{stem}_part001.pdf")
        _write_subset(reader, indices, out_path)
        result.files.append(out_path)
        return result

    if every is not None:
        if every < 1:
            raise PdfToolkitError("--every must be a positive integer")
        part = 0
        for start in range(0, page_count, every):
            part += 1
            chunk = list(range(start, min(start + every, page_count)))
            out_path = os.path.join(outdir, f"{stem}_part{part:03d}.pdf")
            _write_subset(reader, chunk, out_path)
            result.files.append(out_path)
        return result

    # all_pages
    for idx in range(page_count):
        out_path = os.path.join(outdir, f"{stem}_page{idx + 1:03d}.pdf")
        _write_subset(reader, [idx], out_path)
        result.files.append(out_path)
    return result


# --------------------------------------------------------------------------- #
# rotate
# --------------------------------------------------------------------------- #
def rotate(
    in_path: str,
    out_path: str,
    *,
    pages: Optional[str],
    degrees: int,
) -> int:
    """Rotate selected ``pages`` of ``in_path`` by ``degrees`` clockwise.

    ``degrees`` must be a multiple of 90 (positive or negative). If ``pages``
    is None, every page is rotated. Rotation is additive: the new /Rotate is
    the existing value plus ``degrees``, normalised to [0, 360).

    Returns:
        The number of pages rotated.
    """
    if degrees % 90 != 0:
        raise PdfToolkitError(f"--degrees must be a multiple of 90, got {degrees}")

    reader = _open_reader(in_path)
    page_count = len(reader.pages)
    if pages is None:
        targets = set(range(page_count))
    else:
        targets = set(_select_indices(reader, pages))

    writer = PdfWriter()
    for idx, page in enumerate(reader.pages):
        if idx in targets:
            # pypdf's rotate() is additive and normalises modulo 360 internally.
            page.rotate(degrees)
        writer.add_page(page)
    _write(writer, out_path)
    return len(targets)


# --------------------------------------------------------------------------- #
# extract / delete / reorder
# --------------------------------------------------------------------------- #
def extract_pages(in_path: str, out_path: str, *, pages: str) -> int:
    """Write only the selected ``pages`` of ``in_path`` to ``out_path``.

    Returns:
        The number of pages written.
    """
    reader = _open_reader(in_path)
    indices = _select_indices(reader, pages)
    if not indices:
        raise PdfToolkitError("no pages selected for extraction")
    _write_subset(reader, indices, out_path)
    return len(indices)


def delete_pages(in_path: str, out_path: str, *, pages: str) -> int:
    """Write ``in_path`` to ``out_path`` with the selected ``pages`` removed.

    Returns:
        The number of pages remaining in the output.
    """
    reader = _open_reader(in_path)
    page_count = len(reader.pages)
    to_delete = set(_select_indices(reader, pages))
    keep = [i for i in range(page_count) if i not in to_delete]
    if not keep:
        raise PdfToolkitError("refusing to delete every page (output would be empty)")
    _write_subset(reader, keep, out_path)
    return len(keep)


def reorder(in_path: str, out_path: str, *, order: str) -> int:
    """Rewrite ``in_path`` to ``out_path`` with pages in the given ``order``.

    ``order`` is a full permutation/selection selector (e.g. "3,1,2"). Every
    page index it lists is emitted, in that exact sequence; repeats and
    subsets are allowed (so this doubles as a flexible reassembler).

    Returns:
        The number of pages written.
    """
    reader = _open_reader(in_path)
    indices = _select_indices(reader, order)
    if not indices:
        raise PdfToolkitError("no pages specified for reorder")
    _write_subset(reader, indices, out_path)
    return len(indices)


# --------------------------------------------------------------------------- #
# text
# --------------------------------------------------------------------------- #
def text(in_path: str) -> List[str]:
    """Extract plain text from ``in_path``, one string per page.

    Returns:
        A list with one entry per page (possibly empty strings for image-only
        pages). The list length equals the page count.
    """
    reader = _open_reader(in_path)
    pages_text: List[str] = []
    for page in reader.pages:
        try:
            pages_text.append(page.extract_text() or "")
        except Exception:  # pragma: no cover - malformed content stream
            pages_text.append("")
    return pages_text


# --------------------------------------------------------------------------- #
# extract-images
# --------------------------------------------------------------------------- #
@dataclass
class ExtractImagesResult:
    """Outcome of an :func:`extract_images` call."""

    files: List[str] = field(default_factory=list)
    skipped: int = 0  # images that could not be decoded to a file

    def __len__(self) -> int:  # convenience for tests / callers
        return len(self.files)


def _extract_one_image(image: "pikepdf.PdfImage", prefix: str) -> Optional[str]:
    """Write a single embedded image to ``prefix`` + an appropriate suffix.

    Tries pikepdf's fast path (which picks the extension from the image's
    filters, e.g. ``.jpg`` for DCT, ``.png`` for Flate), and falls back to a
    Pillow-encoded PNG for the handful of image types qpdf cannot transcode on
    its own. Returns the written path, or ``None`` if the image is genuinely
    not extractable.
    """
    try:
        return image.extract_to(fileprefix=prefix)
    except (
        pikepdf.UnsupportedImageTypeError,
        pikepdf.HifiPrintImageNotTranscodableError,
        _image_module.NotExtractableError,
        NotImplementedError,
    ):
        try:
            out_path = prefix + ".png"
            image.as_pil_image().save(out_path)
            return out_path
        except Exception:  # pragma: no cover - exotic/broken image stream
            return None


def extract_images(
    in_path: str,
    outdir: str,
    *,
    min_size: int = 0,
) -> ExtractImagesResult:
    """Export every embedded raster image from ``in_path`` into ``outdir``.

    Pages are scanned in order (including images nested inside form XObjects).
    Each distinct image object is written once, even if it is reused on several
    pages, so a repeated logo does not produce a file per page. Output files are
    named ``<stem>_p<NNN>_img<NN>.<ext>`` where ``<NNN>`` is the 1-based page on
    which the image first appears and ``<ext>`` matches the stored encoding.

    Args:
        in_path: source PDF.
        outdir: directory to write images into (created if missing).
        min_size: skip images whose width *or* height is below this many
            pixels (default 0 = keep everything). Handy for dropping 1x1
            spacer pixels.

    Returns:
        An :class:`ExtractImagesResult` listing the written files in order.
    """
    _require_input(in_path)
    if min_size < 0:
        raise PdfToolkitError("--min-size must be zero or a positive integer")

    try:
        pdf = pikepdf.open(in_path)
    except pikepdf.PasswordError as exc:
        raise PdfToolkitError(
            f"{in_path} is password-protected; cannot extract images"
        ) from exc
    except Exception as exc:
        raise PdfToolkitError(f"could not read PDF {in_path}: {exc}") from exc

    result = ExtractImagesResult()
    stem = os.path.splitext(os.path.basename(in_path))[0]

    with pdf:
        os.makedirs(outdir, exist_ok=True)
        seen: set = set()
        for page_number, page in enumerate(pdf.pages, start=1):
            index = 0
            for raw in page.get_images().values():
                # De-duplicate images shared across pages by object identity.
                key = raw.objgen if raw.is_indirect else id(raw)
                if key in seen:
                    continue
                seen.add(key)
                try:
                    image = pikepdf.PdfImage(raw)
                except Exception:  # not an image (e.g. a plain form) - skip
                    continue
                if min_size and (image.width < min_size or image.height < min_size):
                    continue
                index += 1
                prefix = os.path.join(
                    outdir, f"{stem}_p{page_number:03d}_img{index:02d}"
                )
                written = _extract_one_image(image, prefix)
                if written is None:
                    result.skipped += 1
                    index -= 1  # keep numbering gap-free for written files
                else:
                    result.files.append(written)

    return result


# --------------------------------------------------------------------------- #
# info
# --------------------------------------------------------------------------- #
@dataclass
class PdfInfo:
    """Structured result of :func:`info`."""

    path: str
    pages: int
    encrypted: bool
    file_size: int
    page_sizes: List[tuple]  # (width_pt, height_pt) per page, rounded
    metadata: Dict[str, str]
    pdf_version: Optional[str] = None


def info(in_path: str) -> PdfInfo:
    """Gather page count, page sizes, metadata, and encryption status.

    Uses pikepdf for a robust encryption probe and metadata read; falls back
    to reporting an encrypted file without opening its contents.

    Returns:
        A :class:`PdfInfo` dataclass.
    """
    _require_input(in_path)
    file_size = os.path.getsize(in_path)

    # pikepdf reliably reports encryption without needing a password to probe.
    encrypted = False
    pdf_version: Optional[str] = None
    metadata: Dict[str, str] = {}
    page_sizes: List[tuple] = []
    pages = 0

    try:
        with pikepdf.open(in_path) as pdf:
            encrypted = pdf.is_encrypted
            pdf_version = str(pdf.pdf_version)
            pages = len(pdf.pages)
            for page in pdf.pages:
                box = page.mediabox
                width = round(float(box[2]) - float(box[0]), 2)
                height = round(float(box[3]) - float(box[1]), 2)
                page_sizes.append((width, height))
            with pdf.open_metadata() as meta:
                for key in (
                    "dc:title",
                    "dc:creator",
                    "pdf:Producer",
                    "xmp:CreatorTool",
                    "dc:description",
                ):
                    if key in meta:
                        value = meta[key]
                        if isinstance(value, list):
                            value = ", ".join(str(v) for v in value)
                        metadata[key] = str(value)
            # docinfo (older /Info dict) often has more populated fields.
            for k, v in dict(pdf.docinfo).items():
                clean_key = str(k).lstrip("/")
                if clean_key not in metadata:
                    metadata[clean_key] = str(v)
    except pikepdf.PasswordError:
        encrypted = True
    except Exception as exc:
        raise PdfToolkitError(f"could not read PDF {in_path}: {exc}") from exc

    return PdfInfo(
        path=in_path,
        pages=pages,
        encrypted=encrypted,
        file_size=file_size,
        page_sizes=page_sizes,
        metadata=metadata,
        pdf_version=pdf_version,
    )


# --------------------------------------------------------------------------- #
# compress
# --------------------------------------------------------------------------- #
@dataclass
class CompressResult:
    """Outcome of a :func:`compress` call."""

    in_path: str
    out_path: str
    size_before: int
    size_after: int

    @property
    def saved_bytes(self) -> int:
        return self.size_before - self.size_after

    @property
    def ratio(self) -> float:
        """Fraction of the original size saved (negative if it grew)."""
        if self.size_before == 0:
            return 0.0
        return self.saved_bytes / self.size_before


def compress(in_path: str, out_path: str) -> CompressResult:
    """Re-save ``in_path`` with qpdf's space-saving options.

    This is *best effort*. We enable object streams (collapsing many small
    indirect objects into compressed streams) and recompress/normalise
    content streams. For PDFs whose bulk is already-compressed images this
    yields little; for text-heavy or naively-written PDFs it can be
    meaningful. We never let the output exceed the input: if qpdf's result is
    larger, we keep the original bytes so the guarantee "smaller-or-equal"
    always holds.

    Returns:
        A :class:`CompressResult` with before/after sizes.
    """
    _require_input(in_path)
    size_before = os.path.getsize(in_path)
    _ensure_parent_dir(out_path)

    try:
        with pikepdf.open(in_path) as pdf:
            pdf.save(
                out_path,
                object_stream_mode=pikepdf.ObjectStreamMode.generate,
                compress_streams=True,
                recompress_flate=True,
                linearize=False,
            )
    except pikepdf.PasswordError as exc:
        raise PdfToolkitError(
            f"{in_path} is password-protected; cannot compress"
        ) from exc
    except Exception as exc:
        raise PdfToolkitError(f"could not compress {in_path}: {exc}") from exc

    size_after = os.path.getsize(out_path)

    # Guarantee we never make the file bigger. If qpdf's re-save grew it
    # (common for tiny PDFs where object-stream overhead dominates), fall back
    # to a byte-for-byte copy of the original.
    if size_after > size_before:
        with open(in_path, "rb") as src, open(out_path, "wb") as dst:
            dst.write(src.read())
        size_after = os.path.getsize(out_path)

    return CompressResult(
        in_path=in_path,
        out_path=out_path,
        size_before=size_before,
        size_after=size_after,
    )
