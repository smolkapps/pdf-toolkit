"""pdftoolkit: a complete, offline command-line toolkit for manipulating PDFs."""

from .core import (
    PdfToolkitError,
    compress,
    delete_pages,
    extract_pages,
    info,
    merge,
    reorder,
    rotate,
    split,
    text,
)

__version__ = "0.1.0"

__all__ = [
    "PdfToolkitError",
    "compress",
    "delete_pages",
    "extract_pages",
    "info",
    "merge",
    "reorder",
    "rotate",
    "split",
    "text",
    "__version__",
]
