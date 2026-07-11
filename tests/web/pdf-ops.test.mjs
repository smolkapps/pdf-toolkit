// End-to-end tests for the web app's PDF operations, run against the
// vendored pdf-lib bundle — the exact code the browser executes. Fixture
// documents are built in-memory with distinct page widths (page N is
// 100 + 10*N points wide) so tests can verify page ORDER, not just counts.
import { test, before } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
globalThis.PDFLib = require("../../docs/vendor/pdf-lib.min.js");

const ops = await import("../../docs/js/pdf-ops.js");

// A 1-page PDF encrypted with a real user password (AES-256), generated with
// pikepdf and inlined so the suite needs no binary fixture files.
const ENCRYPTED_B64 =
  "JVBERi0xLjcKJb/3ov4KMSAwIG9iago8PCAvRXh0ZW5zaW9ucyA8PCAvQURCRSA8PCAvQmFzZVZlcnNpb24gLzEuNyAvRXh0ZW5zaW9uTGV2ZWwgOCA+PiA+PiAvUGFnZXMgMiAwIFIgL1R5cGUgL0NhdGFsb2cgPj4KZW5kb2JqCjIgMCBvYmoKPDwgL0NvdW50IDEgL0tpZHMgWyAzIDAgUiBdIC9UeXBlIC9QYWdlcyA+PgplbmRvYmoKMyAwIG9iago8PCAvQ29udGVudHMgNCAwIFIgL01lZGlhQm94IFsgMCAwIDIwMCAyMDAgXSAvUGFyZW50IDIgMCBSIC9SZXNvdXJjZXMgPDwgPj4gL1R5cGUgL1BhZ2UgPj4KZW5kb2JqCjQgMCBvYmoKPDwgL0xlbmd0aCAzMiAvRmlsdGVyIC9GbGF0ZURlY29kZSA+PgpzdHJlYW0KJYpt05/yWZsUDJC8IL97QQ/Wla43eyBJcGdMuykIiPMKZW5kc3RyZWFtCmVuZG9iago1IDAgb2JqCjw8IC9DRiA8PCAvU3RkQ0YgPDwgL0F1dGhFdmVudCAvRG9jT3BlbiAvQ0ZNIC9BRVNWMyAvTGVuZ3RoIDMyID4+ID4+IC9GaWx0ZXIgL1N0YW5kYXJkIC9MZW5ndGggMjU2IC9PIDw1NzU2ZTA5YTRmNzFiYWFjMzExZWQzYTJjMjU0MTYxMzAzOGEzNzI0NzU2OTE0YTNkZmQ2Y2JkMDUxMzQ2MzFjYThhMjMxZjE2ZTU0OTgxMGJkYzQyYWNjNDdlNGM4ZDk+IC9PRSA8YmM5YTMxY2VlNzJlNDlkN2I0OWNmZGUzZjA1MmYzNTNkYzZkNGZlNmI2ZWJjYmEyYjZlODE1MTEzOGY2OTBiYj4gL1AgLTEwMjggL1Blcm1zIDwzNjRjOTZkYWM1YTA0MjU1NDlkOGE0OTI4ZGE5OGRkND4gL1IgNiAvU3RtRiAvU3RkQ0YgL1N0ckYgL1N0ZENGIC9VIDwwOTJmMTFiZDljNzNiMTE0MzJlNGVhZjBlNGMwNThiMGRhMzU5MzBmOWU3NTQwYzM4YjA3ZGU1NGU5OWRlYzkwOTYxM2NmNTY2ZmNiNGIzZDM1Zjk4OWVlNzQ5MmNkYjQ+IC9VRSA8MjI5ZjU5ZWRhMTRiMTdmM2I3NjdiOGIzOWNlOWUxODIyZTkyMGIxMGE4M2I1MGM4N2E2OTFlOGFjMGZjZDI5ZT4gL1YgNSA+PgplbmRvYmoKeHJlZgowIDYKMDAwMDAwMDAwMCA2NTUzNSBmIAowMDAwMDAwMDE1IDAwMDAwIG4gCjAwMDAwMDAxMzAgMDAwMDAgbiAKMDAwMDAwMDE4OSAwMDAwMCBuIAowMDAwMDAwMjk1IDAwMDAwIG4gCjAwMDAwMDAzOTggMDAwMDAgbiAKdHJhaWxlciA8PCAvUm9vdCAxIDAgUiAvU2l6ZSA2IC9JRCBbPDljOTlkOGY2YzgxMDk2NjJlMjQ2NzgxNDllMGM3MTMwPjw5Yzk5ZDhmNmM4MTA5NjYyZTI0Njc4MTQ5ZTBjNzEzMD5dIC9FbmNyeXB0IDUgMCBSID4+CnN0YXJ0eHJlZgo5NDgKJSVFT0YK";

function encryptedBytes() {
  return new Uint8Array(Buffer.from(ENCRYPTED_B64, "base64"));
}

/** Build an n-page PDF; page N (1-based) is 100 + 10*N points wide. */
async function makePdf(n, meta = {}) {
  const doc = await globalThis.PDFLib.PDFDocument.create();
  for (let i = 1; i <= n; i++) {
    doc.addPage([100 + 10 * i, 300]);
  }
  if (meta.title) doc.setTitle(meta.title);
  if (meta.author) doc.setAuthor(meta.author);
  return doc.save();
}

/** Read back the 1-based page numbers of a produced PDF via page widths. */
async function pageMarkers(bytes) {
  const doc = await globalThis.PDFLib.PDFDocument.load(bytes);
  return doc.getPages().map((p) => Math.round((p.getSize().width - 100) / 10));
}

async function rotations(bytes) {
  const doc = await globalThis.PDFLib.PDFDocument.load(bytes);
  return doc.getPages().map((p) => p.getRotation().angle);
}

let five;
before(async () => {
  five = await makePdf(5);
});

/* pageCount ---------------------------------------------------------- */

test("pageCount reads the page count", async () => {
  assert.equal(await ops.pageCount(five, "five.pdf"), 5);
});

test("garbage bytes are rejected with a friendly message", async () => {
  await assert.rejects(
    ops.pageCount(new TextEncoder().encode("not a pdf at all"), "junk.pdf"),
    /junk\.pdf.*valid PDF/
  );
});

test("password-protected PDFs are refused, not mangled", async () => {
  await assert.rejects(
    ops.pageCount(encryptedBytes(), "secret.pdf"),
    /password-protected/
  );
});

/* merge --------------------------------------------------------------- */

test("merge concatenates files in order", async () => {
  const two = await makePdf(2);
  const { bytes, pages } = await ops.merge([
    { name: "five.pdf", bytes: five },
    { name: "two.pdf", bytes: two },
  ]);
  assert.equal(pages, 7);
  assert.deepEqual(await pageMarkers(bytes), [1, 2, 3, 4, 5, 1, 2]);
});

test("merge with no files is an error", async () => {
  await assert.rejects(ops.merge([]), /at least one file/);
});

/* split ---------------------------------------------------------------- */

test("split by ranges produces one part with the selected pages", async () => {
  const outputs = await ops.split(five, "five.pdf", { ranges: "1-3,5" });
  assert.equal(outputs.length, 1);
  assert.equal(outputs[0].name, "five_part001.pdf");
  assert.deepEqual(await pageMarkers(outputs[0].bytes), [1, 2, 3, 5]);
});

test("split every 2 pages chunks the document", async () => {
  const outputs = await ops.split(five, "five.pdf", { every: 2 });
  assert.deepEqual(
    outputs.map((o) => o.name),
    ["five_part001.pdf", "five_part002.pdf", "five_part003.pdf"]
  );
  assert.deepEqual(await pageMarkers(outputs[0].bytes), [1, 2]);
  assert.deepEqual(await pageMarkers(outputs[1].bytes), [3, 4]);
  assert.deepEqual(await pageMarkers(outputs[2].bytes), [5]);
});

test("split all bursts into one file per page", async () => {
  const outputs = await ops.split(five, "five.pdf", { all: true });
  assert.equal(outputs.length, 5);
  assert.equal(outputs[3].name, "five_page004.pdf");
  assert.deepEqual(await pageMarkers(outputs[3].bytes), [4]);
});

test("split rejects bad chunk sizes and bad selectors", async () => {
  await assert.rejects(ops.split(five, "five.pdf", { every: 0 }), /positive/);
  await assert.rejects(ops.split(five, "five.pdf", { ranges: "9" }), /out of range/);
});

/* rotate ---------------------------------------------------------------- */

test("rotate turns only the selected pages, additively", async () => {
  const { bytes, rotated } = await ops.rotate(five, "five.pdf", "1,3", 90);
  assert.equal(rotated, 2);
  assert.deepEqual(await rotations(bytes), [90, 0, 90, 0, 0]);

  const again = await ops.rotate(bytes, "five.pdf", "1", 90);
  assert.deepEqual(await rotations(again.bytes), [180, 0, 90, 0, 0]);
});

test("rotate with a blank selector rotates every page", async () => {
  const { bytes, rotated } = await ops.rotate(five, "five.pdf", "  ", -90);
  assert.equal(rotated, 5);
  assert.deepEqual(await rotations(bytes), [270, 270, 270, 270, 270]);
});

test("rotate rejects non-multiples of 90", async () => {
  await assert.rejects(ops.rotate(five, "five.pdf", null, 45), /multiple of 90/);
});

/* extract / delete / reorder --------------------------------------------- */

test("extractPages keeps only the selection, in selector order", async () => {
  const { bytes, pages } = await ops.extractPages(five, "five.pdf", "2-4");
  assert.equal(pages, 3);
  assert.deepEqual(await pageMarkers(bytes), [2, 3, 4]);
});

test("deletePages removes the selection and keeps the rest in order", async () => {
  const { bytes, pages } = await ops.deletePages(five, "five.pdf", "2,4");
  assert.equal(pages, 3);
  assert.deepEqual(await pageMarkers(bytes), [1, 3, 5]);
});

test("deleting every page is refused", async () => {
  await assert.rejects(ops.deletePages(five, "five.pdf", "1-5"), /every page/);
});

test("reorder follows the selector exactly, repeats allowed", async () => {
  const { bytes } = await ops.reorder(five, "five.pdf", "3,1,2,3");
  assert.deepEqual(await pageMarkers(bytes), [3, 1, 2, 3]);
});

test("a descending range reverses the document", async () => {
  const { bytes } = await ops.reorder(five, "five.pdf", "5-1");
  assert.deepEqual(await pageMarkers(bytes), [5, 4, 3, 2, 1]);
});

/* inspect ------------------------------------------------------------------ */

test("inspect reports pages, sizes, and metadata", async () => {
  const bytes = await makePdf(2, { title: "Quarterly Report", author: "Jo Smith" });
  const info = await ops.inspect(bytes, "report.pdf");
  assert.equal(info.pages, 2);
  assert.deepEqual(info.pageSizes, [
    [110, 300],
    [120, 300],
  ]);
  assert.equal(info.metadata.Title, "Quarterly Report");
  assert.equal(info.metadata.Author, "Jo Smith");
});
