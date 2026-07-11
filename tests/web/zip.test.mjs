// Tests for the STORE-only ZIP writer used by the Split tool's
// "download all" button. Verifies the classic CRC-32 test vector and walks
// the archive structure the way an extractor would.
import { test } from "node:test";
import assert from "node:assert/strict";

import { buildZip, crc32 } from "../../docs/js/zip.js";

const encoder = new TextEncoder();

test("crc32 matches the standard test vector", () => {
  assert.equal(crc32(encoder.encode("123456789")), 0xcbf43926);
  assert.equal(crc32(new Uint8Array(0)), 0);
});

test("zip structure is parseable and byte-accurate", () => {
  const entries = [
    { name: "a.pdf", data: encoder.encode("hello pdf one") },
    { name: "b.pdf", data: encoder.encode("second file, longer contents here") },
  ];
  const zip = buildZip(entries, new Date(2024, 0, 2, 3, 4, 6));
  const view = new DataView(zip.buffer);

  // End of central directory record: last 22 bytes.
  const eocd = zip.length - 22;
  assert.equal(view.getUint32(eocd, true), 0x06054b50);
  assert.equal(view.getUint16(eocd + 8, true), 2, "entry count");
  const cdSize = view.getUint32(eocd + 12, true);
  const cdOffset = view.getUint32(eocd + 16, true);
  assert.equal(cdOffset + cdSize + 22, zip.length, "no trailing garbage");

  // Walk the central directory and check each local header + payload.
  let pos = cdOffset;
  for (const entry of entries) {
    assert.equal(view.getUint32(pos, true), 0x02014b50, "central dir signature");
    const crc = view.getUint32(pos + 16, true);
    const size = view.getUint32(pos + 20, true);
    const nameLen = view.getUint16(pos + 28, true);
    const localOffset = view.getUint32(pos + 42, true);
    assert.equal(crc, crc32(entry.data));
    assert.equal(size, entry.data.length);

    const name = new TextDecoder().decode(zip.subarray(pos + 46, pos + 46 + nameLen));
    assert.equal(name, entry.name);

    // Local header: STORE method, then the exact payload bytes.
    assert.equal(view.getUint32(localOffset, true), 0x04034b50);
    assert.equal(view.getUint16(localOffset + 8, true), 0, "method is STORE");
    const localNameLen = view.getUint16(localOffset + 26, true);
    const dataStart = localOffset + 30 + localNameLen;
    assert.deepEqual(
      zip.subarray(dataStart, dataStart + size),
      entry.data,
      "stored payload is byte-identical"
    );
    pos += 46 + nameLen;
  }
});

test("empty archive is still a valid zip", () => {
  const zip = buildZip([], new Date(2024, 0, 2));
  assert.equal(zip.length, 22);
  const view = new DataView(zip.buffer);
  assert.equal(view.getUint32(0, true), 0x06054b50);
  assert.equal(view.getUint16(8, true), 0);
});
