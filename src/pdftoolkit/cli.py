"""Command-line interface for pdftoolkit.

A thin argparse wrapper over :mod:`pdftoolkit.core`. Every subcommand maps to
one library function; the library raises :class:`PdfToolkitError` for any
user-caused failure, which we catch here and turn into exit code 2 with a
message on stderr. Unexpected exceptions propagate (exit 1 with a traceback)
so genuine bugs are not silently swallowed.

Exit codes:
    0  success
    2  user error (bad input, missing file, encrypted PDF, bad page selector)
"""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional, Sequence

from . import __version__
from .core import (
    PdfToolkitError,
    compress,
    delete_pages,
    extract_images,
    extract_pages,
    info,
    merge,
    reorder,
    rotate,
    split,
    text,
)

EXIT_OK = 0
EXIT_USER_ERROR = 2


def _human_size(num_bytes: int) -> str:
    """Format a byte count as a short human-readable string."""
    value = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{num_bytes} B"  # pragma: no cover - unreachable


# --------------------------------------------------------------------------- #
# Subcommand handlers (each returns an int exit code)
# --------------------------------------------------------------------------- #
def _cmd_merge(args: argparse.Namespace) -> int:
    total = merge(args.inputs, args.output)
    print(f"Merged {len(args.inputs)} file(s) -> {args.output} ({total} pages)")
    return EXIT_OK


def _cmd_split(args: argparse.Namespace) -> int:
    outdir = args.outdir or "."
    result = split(
        args.input,
        outdir,
        ranges=args.ranges,
        every=args.every,
        all_pages=args.all,
    )
    print(f"Wrote {len(result)} file(s) to {outdir}:")
    for path in result.files:
        print(f"  {path}")
    return EXIT_OK


def _cmd_rotate(args: argparse.Namespace) -> int:
    count = rotate(args.input, args.output, pages=args.pages, degrees=args.degrees)
    scope = "all pages" if args.pages is None else f"pages {args.pages}"
    print(f"Rotated {count} page(s) ({scope}) by {args.degrees} deg -> {args.output}")
    return EXIT_OK


def _cmd_extract(args: argparse.Namespace) -> int:
    count = extract_pages(args.input, args.output, pages=args.pages)
    print(f"Extracted {count} page(s) [{args.pages}] -> {args.output}")
    return EXIT_OK


def _cmd_delete(args: argparse.Namespace) -> int:
    remaining = delete_pages(args.input, args.output, pages=args.pages)
    print(f"Deleted pages [{args.pages}]; {remaining} page(s) remain -> {args.output}")
    return EXIT_OK


def _cmd_reorder(args: argparse.Namespace) -> int:
    count = reorder(args.input, args.output, order=args.order)
    print(f"Reordered to [{args.order}] ({count} pages) -> {args.output}")
    return EXIT_OK


def _cmd_extract_images(args: argparse.Namespace) -> int:
    outdir = args.outdir or "."
    result = extract_images(args.input, outdir, min_size=args.min_size)
    if not result.files:
        print(f"No embedded images found in {args.input}")
    else:
        print(f"Extracted {len(result.files)} image(s) to {outdir}:")
        for path in result.files:
            print(f"  {path}")
    if result.skipped:
        print(f"  note: skipped {result.skipped} image(s) that could not be decoded")
    return EXIT_OK


def _cmd_text(args: argparse.Namespace) -> int:
    pages = text(args.input)
    for i, page_text in enumerate(pages, start=1):
        print(f"----- Page {i} -----")
        print(page_text)
    return EXIT_OK


def _cmd_info(args: argparse.Namespace) -> int:
    result = info(args.input)
    print(f"File:        {result.path}")
    print(f"Size:        {_human_size(result.file_size)} ({result.file_size} bytes)")
    print(f"PDF version: {result.pdf_version or 'unknown'}")
    print(f"Pages:       {result.pages}")
    print(f"Encrypted:   {'yes' if result.encrypted else 'no'}")
    if result.page_sizes:
        first = result.page_sizes[0]
        uniform = all(s == first for s in result.page_sizes)
        if uniform:
            print(f"Page size:   {first[0]} x {first[1]} pt (all pages)")
        else:
            print("Page sizes:  (varies)")
            for i, size in enumerate(result.page_sizes, start=1):
                print(f"  page {i}: {size[0]} x {size[1]} pt")
    if result.metadata:
        print("Metadata:")
        for key, value in result.metadata.items():
            print(f"  {key}: {value}")
    else:
        print("Metadata:    (none)")
    return EXIT_OK


def _cmd_compress(args: argparse.Namespace) -> int:
    result = compress(args.input, args.output)
    pct = result.ratio * 100
    print(
        f"Compressed {args.input} -> {args.output}\n"
        f"  before: {_human_size(result.size_before)} "
        f"({result.size_before} bytes)\n"
        f"  after:  {_human_size(result.size_after)} "
        f"({result.size_after} bytes)\n"
        f"  saved:  {_human_size(result.saved_bytes)} ({pct:.1f}%)"
    )
    if result.saved_bytes <= 0:
        print(
            "  note: this PDF was already well-compressed; output kept "
            "smaller-or-equal."
        )
    return EXIT_OK


# --------------------------------------------------------------------------- #
# Argument parser
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    """Construct the full argparse parser tree."""
    parser = argparse.ArgumentParser(
        prog="pdftoolkit",
        description="A complete, offline toolkit for manipulating PDF files.",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    sub = parser.add_subparsers(dest="command", metavar="<command>")
    sub.required = True

    # merge
    p_merge = sub.add_parser("merge", help="concatenate PDFs into one")
    p_merge.add_argument("inputs", nargs="+", help="input PDF files, in order")
    p_merge.add_argument("-o", "--output", required=True, help="output PDF path")
    p_merge.set_defaults(func=_cmd_merge)

    # split
    p_split = sub.add_parser("split", help="split a PDF into multiple files")
    p_split.add_argument("input", help="input PDF file")
    mode = p_split.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--ranges", help='page ranges to extract as one file, e.g. "1-3,5"'
    )
    mode.add_argument(
        "--every", type=int, metavar="N", help="split into chunks of N pages"
    )
    mode.add_argument("--all", action="store_true", help="one output file per page")
    p_split.add_argument(
        "--outdir", default=".", help="output directory (default: current dir)"
    )
    p_split.set_defaults(func=_cmd_split)

    # rotate
    p_rotate = sub.add_parser("rotate", help="rotate pages")
    p_rotate.add_argument("input", help="input PDF file")
    p_rotate.add_argument(
        "--pages", default=None, help='pages to rotate, e.g. "1,2" (default: all)'
    )
    p_rotate.add_argument(
        "--degrees",
        type=int,
        required=True,
        help="clockwise rotation, multiple of 90 (e.g. 90, 180, -90)",
    )
    p_rotate.add_argument("-o", "--output", required=True, help="output PDF path")
    p_rotate.set_defaults(func=_cmd_rotate)

    # extract
    p_extract = sub.add_parser("extract", help="extract a subset of pages")
    p_extract.add_argument("input", help="input PDF file")
    p_extract.add_argument("--pages", required=True, help='pages to keep, e.g. "2-4"')
    p_extract.add_argument("-o", "--output", required=True, help="output PDF path")
    p_extract.set_defaults(func=_cmd_extract)

    # delete
    p_delete = sub.add_parser("delete", help="remove a subset of pages")
    p_delete.add_argument("input", help="input PDF file")
    p_delete.add_argument("--pages", required=True, help='pages to remove, e.g. "3"')
    p_delete.add_argument("-o", "--output", required=True, help="output PDF path")
    p_delete.set_defaults(func=_cmd_delete)

    # reorder
    p_reorder = sub.add_parser("reorder", help="reorder pages")
    p_reorder.add_argument("input", help="input PDF file")
    p_reorder.add_argument(
        "--order", required=True, help='new page order, e.g. "3,1,2"'
    )
    p_reorder.add_argument("-o", "--output", required=True, help="output PDF path")
    p_reorder.set_defaults(func=_cmd_reorder)

    # extract-images
    p_imgs = sub.add_parser(
        "extract-images", help="export embedded raster images to files"
    )
    p_imgs.add_argument("input", help="input PDF file")
    p_imgs.add_argument(
        "--outdir", default=".", help="output directory (default: current dir)"
    )
    p_imgs.add_argument(
        "--min-size",
        type=int,
        default=0,
        metavar="N",
        dest="min_size",
        help="skip images narrower or shorter than N pixels (default: 0)",
    )
    p_imgs.set_defaults(func=_cmd_extract_images)

    # text
    p_text = sub.add_parser("text", help="extract plain text, per page")
    p_text.add_argument("input", help="input PDF file")
    p_text.set_defaults(func=_cmd_text)

    # info
    p_info = sub.add_parser("info", help="show page count, size, metadata")
    p_info.add_argument("input", help="input PDF file")
    p_info.set_defaults(func=_cmd_info)

    # compress
    p_compress = sub.add_parser("compress", help="re-save with compression")
    p_compress.add_argument("input", help="input PDF file")
    p_compress.add_argument("-o", "--output", required=True, help="output PDF path")
    p_compress.set_defaults(func=_cmd_compress)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Entry point. Returns a process exit code (does not call sys.exit)."""
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except PdfToolkitError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USER_ERROR


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
