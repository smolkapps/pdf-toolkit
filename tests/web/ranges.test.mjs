// Tests for the web app's page-selector parser. Mirrors tests/test_ranges.py
// so the browser and the CLI stay in lock-step on selector semantics.
import { test } from "node:test";
import assert from "node:assert/strict";

import { parsePages, RangeError_ } from "../../docs/js/ranges.js";

test("single page", () => {
  assert.deepEqual(parsePages("3", 10), [2]);
});

test("ascending range is inclusive", () => {
  assert.deepEqual(parsePages("2-4", 10), [1, 2, 3]);
});

test("comma list", () => {
  assert.deepEqual(parsePages("1,3,5", 10), [0, 2, 4]);
});

test("mixed list and ranges", () => {
  assert.deepEqual(parsePages("1-3,5,7-8", 10), [0, 1, 2, 4, 6, 7]);
});

test("descending range expands backwards", () => {
  assert.deepEqual(parsePages("4-2", 10), [3, 2, 1]);
});

test("whitespace is ignored", () => {
  assert.deepEqual(parsePages(" 1 , 3 - 4 ", 10), [0, 2, 3]);
});

test("duplicates are preserved", () => {
  assert.deepEqual(parsePages("1,1", 10), [0, 0]);
});

test("single-page span", () => {
  assert.deepEqual(parsePages("3-3", 10), [2]);
});

test("full-document selector", () => {
  assert.deepEqual(parsePages("1-3", 3), [0, 1, 2]);
});

for (const bad of ["", "   ", ",", "1,,2", "a", "1-2-3", "-3", "3-", "0", "-1", "1.5"]) {
  test(`rejects malformed selector ${JSON.stringify(bad)}`, () => {
    assert.throws(() => parsePages(bad, 10), RangeError_);
  });
}

test("rejects page beyond document end", () => {
  assert.throws(() => parsePages("11", 10), /out of range/);
  assert.throws(() => parsePages("1-11", 10), /out of range/);
});

test("error message counts pages correctly for 1-page docs", () => {
  assert.throws(() => parsePages("2", 1), /document has 1 page\)/);
});

test("rejects any selector against an empty document", () => {
  assert.throws(() => parsePages("1", 0), /no pages/);
});

test("rejects null and undefined", () => {
  assert.throws(() => parsePages(null, 10), /no pages specified/);
  assert.throws(() => parsePages(undefined, 10), /no pages specified/);
});
