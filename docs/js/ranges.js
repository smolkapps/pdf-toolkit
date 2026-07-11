/* Parsing of human-friendly, 1-based page selectors into 0-based indices.
 *
 * This is a faithful port of the CLI's `pdftoolkit.ranges` module so the web
 * app and the command line accept exactly the same syntax:
 *
 *   "3"          a single page
 *   "2-4"        a contiguous, inclusive range
 *   "1,3,5"      a comma-separated list
 *   "1-3,5,7-8"  any combination of the above
 *
 * Whitespace around tokens and commas is ignored. Reversed ranges such as
 * "4-2" are accepted and expand descending (4, 3, 2), which is what a user
 * who types them almost always means (e.g. for reorder).
 */

export class RangeError_ extends Error {
  constructor(message) {
    super(message);
    this.name = "RangeError";
  }
}

function parseSingle(token, pageCount, selector) {
  if (!/^\d+$/.test(token)) {
    throw new RangeError_(`invalid page number "${token}" in "${selector}"`);
  }
  const value = parseInt(token, 10);
  if (value < 1) {
    throw new RangeError_(`page numbers start at 1, got ${value} in "${selector}"`);
  }
  if (value > pageCount) {
    throw new RangeError_(
      `page ${value} out of range (document has ${pageCount} page` +
        `${pageCount !== 1 ? "s" : ""})`
    );
  }
  return value;
}

function parseSpan(token, pageCount, selector) {
  const parts = token.split("-");
  if (parts.length !== 2) {
    throw new RangeError_(`invalid range "${token}" in "${selector}"`);
  }
  const startS = parts[0].trim();
  const endS = parts[1].trim();
  if (!startS || !endS) {
    throw new RangeError_(
      `open-ended range "${token}" in "${selector}"; both ends are required (e.g. "2-4")`
    );
  }
  const start = parseSingle(startS, pageCount, selector);
  const end = parseSingle(endS, pageCount, selector);
  const indices = [];
  if (start <= end) {
    for (let i = start; i <= end; i++) indices.push(i - 1);
  } else {
    for (let i = start; i >= end; i--) indices.push(i - 1);
  }
  return indices;
}

/**
 * Parse a 1-based page selector into an array of 0-based page indices.
 *
 * Duplicates are preserved (so "1,1" yields [0, 0]); callers that need
 * uniqueness should de-duplicate themselves. Throws RangeError_ on empty
 * input, malformed tokens, zero/negative page numbers, or numbers exceeding
 * pageCount.
 */
export function parsePages(selector, pageCount) {
  if (selector === null || selector === undefined) {
    throw new RangeError_("no pages specified");
  }
  const text = String(selector).trim();
  if (!text) {
    throw new RangeError_("no pages specified");
  }
  if (pageCount < 1) {
    throw new RangeError_("document has no pages");
  }

  const indices = [];
  for (const rawToken of text.split(",")) {
    const token = rawToken.trim();
    if (!token) {
      throw new RangeError_(`empty page token in "${selector}"`);
    }
    if (token.includes("-")) {
      indices.push(...parseSpan(token, pageCount, selector));
    } else {
      indices.push(parseSingle(token, pageCount, selector) - 1);
    }
  }
  return indices;
}
