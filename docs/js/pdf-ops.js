/* Core PDF operations for the web app, mirroring the CLI's behaviour.
 *
 * Every function is pure: bytes in, bytes out. All of them run entirely in
 * the browser via pdf-lib — no upload, no network. The pdf-lib UMD global is
 * read lazily from globalThis so these functions are testable in Node.
 *
 * User-caused failures (encrypted input, bad selector, empty result) throw
 * PdfToolkitError with a plain-English message the UI shows verbatim.
 */

import { parsePages, RangeError_ } from "./ranges.js";

export class PdfToolkitError extends Error {
  constructor(message) {
    super(message);
    this.name = "PdfToolkitError";
  }
}

function lib() {
  const pdfLib = globalThis.PDFLib;
  if (!pdfLib) {
    throw new PdfToolkitError(
      "the PDF engine failed to load — reload the page and try again"
    );
  }
  return pdfLib;
}

async function loadDoc(bytes, name) {
  const { PDFDocument } = lib();
  let doc;
  try {
    doc = await PDFDocument.load(bytes, { ignoreEncryption: true });
  } catch (err) {
    throw new PdfToolkitError(
      `could not read ${name}: it does not look like a valid PDF`
    );
  }
  if (doc.isEncrypted) {
    throw new PdfToolkitError(
      `${name} is password-protected; decrypt it first (this tool does not accept passwords)`
    );
  }
  if (doc.getPageCount() === 0) {
    throw new PdfToolkitError(`${name} has no pages`);
  }
  return doc;
}

function selectIndices(selector, pageCount) {
  try {
    return parsePages(selector, pageCount);
  } catch (err) {
    if (err instanceof RangeError_) throw new PdfToolkitError(err.message);
    throw err;
  }
}

/** Return the page count of a PDF, throwing PdfToolkitError on bad input. */
export async function pageCount(bytes, name) {
  const doc = await loadDoc(bytes, name);
  return doc.getPageCount();
}

/**
 * Inspect a PDF: page count, per-page sizes in points, and document
 * metadata. Mirrors the CLI's `info` command.
 */
export async function inspect(bytes, name) {
  const doc = await loadDoc(bytes, name);
  const pages = doc.getPages();
  const pageSizes = pages.map((page) => {
    const { width, height } = page.getSize();
    return [Math.round(width * 100) / 100, Math.round(height * 100) / 100];
  });
  const metadata = {};
  const fields = [
    ["Title", () => doc.getTitle()],
    ["Author", () => doc.getAuthor()],
    ["Subject", () => doc.getSubject()],
    ["Keywords", () => doc.getKeywords()],
    ["Creator", () => doc.getCreator()],
    ["Producer", () => doc.getProducer()],
    ["Created", () => doc.getCreationDate()?.toISOString()],
    ["Modified", () => doc.getModificationDate()?.toISOString()],
  ];
  for (const [label, get] of fields) {
    let value;
    try {
      value = get();
    } catch {
      continue; // malformed metadata entry — skip it, never fail inspect
    }
    if (value !== undefined && value !== null && String(value).trim() !== "") {
      metadata[label] = String(value);
    }
  }
  return { pages: pages.length, pageSizes, metadata };
}

async function copyIndices(srcDoc, indices) {
  const { PDFDocument } = lib();
  const out = await PDFDocument.create();
  const copied = await out.copyPages(srcDoc, indices);
  for (const page of copied) out.addPage(page);
  return out.save();
}

/** Concatenate several PDFs, in order, into one. */
export async function merge(files) {
  if (!files.length) {
    throw new PdfToolkitError("merge needs at least one file");
  }
  const { PDFDocument } = lib();
  const out = await PDFDocument.create();
  let total = 0;
  for (const file of files) {
    const doc = await loadDoc(file.bytes, file.name);
    const indices = doc.getPageIndices();
    const copied = await out.copyPages(doc, indices);
    for (const page of copied) out.addPage(page);
    total += indices.length;
  }
  return { bytes: await out.save(), pages: total };
}

/**
 * Split one PDF into one or more PDFs.
 * mode: {ranges: "1-3,5"} | {every: N} | {all: true}
 * Returns [{name, bytes}] using the CLI's part/page naming scheme.
 */
export async function split(bytes, name, mode) {
  const doc = await loadDoc(bytes, name);
  const total = doc.getPageCount();
  const stem = name.replace(/\.pdf$/i, "");
  const outputs = [];

  if (mode.ranges !== undefined) {
    const indices = selectIndices(mode.ranges, total);
    outputs.push({
      name: `${stem}_part001.pdf`,
      bytes: await copyIndices(doc, indices),
    });
    return outputs;
  }

  if (mode.every !== undefined) {
    const every = mode.every;
    if (!Number.isInteger(every) || every < 1) {
      throw new PdfToolkitError("pages per file must be a positive whole number");
    }
    let part = 0;
    for (let start = 0; start < total; start += every) {
      part += 1;
      const chunk = [];
      for (let i = start; i < Math.min(start + every, total); i++) chunk.push(i);
      outputs.push({
        name: `${stem}_part${String(part).padStart(3, "0")}.pdf`,
        bytes: await copyIndices(doc, chunk),
      });
    }
    return outputs;
  }

  if (mode.all) {
    for (let i = 0; i < total; i++) {
      outputs.push({
        name: `${stem}_page${String(i + 1).padStart(3, "0")}.pdf`,
        bytes: await copyIndices(doc, [i]),
      });
    }
    return outputs;
  }

  throw new PdfToolkitError("choose a split mode first");
}

/**
 * Rotate selected pages (or all pages when selector is blank) by a multiple
 * of 90 degrees, clockwise. Rotation is additive, matching the CLI.
 */
export async function rotate(bytes, name, selector, deg) {
  if (deg % 90 !== 0) {
    throw new PdfToolkitError(`rotation must be a multiple of 90, got ${deg}`);
  }
  const { degrees } = lib();
  const doc = await loadDoc(bytes, name);
  const total = doc.getPageCount();
  const targets = new Set(
    selector && selector.trim()
      ? selectIndices(selector, total)
      : Array.from({ length: total }, (_, i) => i)
  );
  const pages = doc.getPages();
  for (const idx of targets) {
    const page = pages[idx];
    const current = page.getRotation().angle;
    page.setRotation(degrees((((current + deg) % 360) + 360) % 360));
  }
  return { bytes: await doc.save(), rotated: targets.size };
}

/** Keep only the selected pages. */
export async function extractPages(bytes, name, selector) {
  const doc = await loadDoc(bytes, name);
  const indices = selectIndices(selector, doc.getPageCount());
  if (!indices.length) throw new PdfToolkitError("no pages selected");
  return { bytes: await copyIndices(doc, indices), pages: indices.length };
}

/** Remove the selected pages, keeping the rest in order. */
export async function deletePages(bytes, name, selector) {
  const doc = await loadDoc(bytes, name);
  const total = doc.getPageCount();
  const toDelete = new Set(selectIndices(selector, total));
  const keep = [];
  for (let i = 0; i < total; i++) if (!toDelete.has(i)) keep.push(i);
  if (!keep.length) {
    throw new PdfToolkitError(
      "refusing to delete every page (output would be empty)"
    );
  }
  return { bytes: await copyIndices(doc, keep), pages: keep.length };
}

/**
 * Rewrite pages in the given order. Repeats and subsets are allowed, so this
 * doubles as a flexible reassembler (e.g. "3,1,2" or "5-1" to reverse).
 */
export async function reorder(bytes, name, selector) {
  const doc = await loadDoc(bytes, name);
  const indices = selectIndices(selector, doc.getPageCount());
  if (!indices.length) throw new PdfToolkitError("no pages specified");
  return { bytes: await copyIndices(doc, indices), pages: indices.length };
}
