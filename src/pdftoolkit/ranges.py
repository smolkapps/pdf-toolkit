"""Parsing of human-friendly, 1-based page selectors into 0-based indices.

Supported selector syntax (all 1-based, inclusive):
    "3"          -> a single page
    "2-4"        -> a contiguous, inclusive range
    "1,3,5"      -> a comma-separated list
    "1-3,5,7-8"  -> any combination of the above

Whitespace around tokens and commas is ignored. Reversed ranges such as
"4-2" are accepted and expand descending (4, 3, 2), which is what a user who
types them almost always means (e.g. for `reorder`).
"""

from __future__ import annotations

from typing import List


class RangeError(ValueError):
    """Raised when a page selector string cannot be parsed."""


def parse_pages(selector: str, page_count: int) -> List[int]:
    """Parse a 1-based page selector into a list of 0-based page indices.

    Args:
        selector: e.g. "1-3,5". Must be non-empty.
        page_count: total number of pages in the document, used for bounds
            checking and to honour the convention that omitting nothing.

    Returns:
        A list of 0-based indices in the order the user specified them.
        Duplicates are preserved (so "1,1" yields [0, 0]); callers that need
        uniqueness should de-duplicate themselves.

    Raises:
        RangeError: on empty input, malformed tokens, non-integer values,
            zero/negative page numbers, or numbers exceeding ``page_count``.
    """
    if selector is None:
        raise RangeError("no pages specified")
    text = selector.strip()
    if not text:
        raise RangeError("no pages specified")
    if page_count < 1:
        raise RangeError("document has no pages")

    indices: List[int] = []
    for raw_token in text.split(","):
        token = raw_token.strip()
        if not token:
            raise RangeError(f"empty page token in {selector!r}")
        if "-" in token:
            indices.extend(_parse_span(token, page_count, selector))
        else:
            indices.append(_parse_single(token, page_count, selector) - 1)
    return indices


def _parse_single(token: str, page_count: int, selector: str) -> int:
    """Parse a bare integer token into a validated 1-based page number."""
    try:
        value = int(token)
    except ValueError as exc:
        raise RangeError(f"invalid page number {token!r} in {selector!r}") from exc
    if value < 1:
        raise RangeError(f"page numbers start at 1, got {value} in {selector!r}")
    if value > page_count:
        raise RangeError(
            f"page {value} out of range (document has {page_count} page"
            f"{'s' if page_count != 1 else ''})"
        )
    return value


def _parse_span(token: str, page_count: int, selector: str) -> List[int]:
    """Parse an "a-b" span into a list of 0-based indices (inclusive)."""
    parts = token.split("-")
    if len(parts) != 2:
        raise RangeError(f"invalid range {token!r} in {selector!r}")
    start_s, end_s = parts[0].strip(), parts[1].strip()
    if not start_s or not end_s:
        raise RangeError(
            f"open-ended range {token!r} in {selector!r}; "
            f"both ends are required (e.g. '2-4')"
        )
    start = _parse_single(start_s, page_count, selector)
    end = _parse_single(end_s, page_count, selector)
    if start <= end:
        return [i - 1 for i in range(start, end + 1)]
    # Descending range, e.g. "4-2" -> [3, 2, 1].
    return [i - 1 for i in range(start, end - 1, -1)]
