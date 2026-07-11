/* UI wiring for PDF Toolkit. All processing happens in pdf-ops.js, locally. */

import * as ops from "./pdf-ops.js";
import { parsePages, RangeError_ } from "./ranges.js";
import { buildZip } from "./zip.js";

const $ = (id) => document.getElementById(id);

/* ------------------------------------------------------------------ */
/* Small helpers                                                       */
/* ------------------------------------------------------------------ */

function fmtSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function plural(n, word) {
  return `${n} ${word}${n === 1 ? "" : "s"}`;
}

function readFileBytes(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(new Uint8Array(reader.result));
    reader.onerror = () => reject(new Error(`could not read ${file.name}`));
    reader.readAsArrayBuffer(file);
  });
}

function setStatus(el, state, message) {
  el.className = "status" + (state ? ` status-${state}` : "");
  el.innerHTML = "";
  if (!message) return;
  if (state === "busy") {
    const spinner = document.createElement("span");
    spinner.className = "spinner";
    spinner.setAttribute("aria-hidden", "true");
    el.appendChild(spinner);
  }
  el.appendChild(document.createTextNode(message));
}

let toastTimer;
function showToast(message) {
  const toast = $("toast");
  toast.textContent = message;
  toast.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toast.hidden = true;
  }, 2600);
}

const liveUrls = new Map(); // results container -> [blob urls]

function renderResults(container, outputs, summary) {
  for (const url of liveUrls.get(container) || []) URL.revokeObjectURL(url);
  const urls = [];
  container.innerHTML = "";

  const heading = document.createElement("p");
  heading.className = "results-summary";
  heading.textContent = summary;
  container.appendChild(heading);

  const list = document.createElement("ul");
  list.className = "download-list";
  for (const out of outputs) {
    const blob = new Blob([out.bytes], { type: "application/pdf" });
    const url = URL.createObjectURL(blob);
    urls.push(url);
    const li = document.createElement("li");
    const a = document.createElement("a");
    a.href = url;
    a.download = out.name;
    a.className = "btn btn-download";
    a.innerHTML =
      '<svg aria-hidden="true" viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12m0 0 4-4m-4 4-4-4"/><path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"/></svg> ';
    a.appendChild(document.createTextNode(out.name));
    const size = document.createElement("span");
    size.className = "dl-size";
    size.textContent = fmtSize(out.bytes.length);
    li.appendChild(a);
    li.appendChild(size);
    list.appendChild(li);
  }
  container.appendChild(list);

  if (outputs.length > 1) {
    const zipBytes = buildZip(
      outputs.map((o) => ({ name: o.name, data: o.bytes }))
    );
    const zipBlob = new Blob([zipBytes], { type: "application/zip" });
    const zipUrl = URL.createObjectURL(zipBlob);
    urls.push(zipUrl);
    const a = document.createElement("a");
    a.href = zipUrl;
    a.download = "pdf-toolkit-output.zip";
    a.className = "btn btn-primary btn-zip";
    a.textContent = `Download all ${outputs.length} as ZIP (${fmtSize(zipBytes.length)})`;
    container.appendChild(a);
  }
  liveUrls.set(container, urls);
}

function selectorError(selector, pageCount, { required = true, label = "pages" } = {}) {
  const text = (selector || "").trim();
  if (!text) return required ? `Enter the ${label} first (e.g. 1-3,5).` : null;
  try {
    parsePages(text, pageCount);
    return null;
  } catch (err) {
    if (err instanceof RangeError_) return err.message;
    throw err;
  }
}

function isPdfFile(file) {
  return (
    file.type === "application/pdf" || /\.pdf$/i.test(file.name || "")
  );
}

/* ------------------------------------------------------------------ */
/* Drop zones                                                          */
/* ------------------------------------------------------------------ */

function wireDropzone(zone, input, onFiles) {
  const openPicker = () => input.click();
  zone.addEventListener("click", (event) => {
    if (event.target !== input) openPicker();
  });
  zone.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      openPicker();
    }
  });
  input.addEventListener("change", () => {
    if (input.files.length) onFiles(Array.from(input.files));
    input.value = "";
  });
  for (const type of ["dragenter", "dragover"]) {
    zone.addEventListener(type, (event) => {
      event.preventDefault();
      zone.classList.add("drag-over");
    });
  }
  zone.addEventListener("dragleave", () => zone.classList.remove("drag-over"));
  zone.addEventListener("drop", (event) => {
    event.preventDefault();
    zone.classList.remove("drag-over");
    const files = Array.from(event.dataTransfer.files || []);
    if (files.length) onFiles(files);
  });
}

// Don't let a stray drop outside a zone navigate away from the app.
window.addEventListener("dragover", (event) => event.preventDefault());
window.addEventListener("drop", (event) => event.preventDefault());

/* ------------------------------------------------------------------ */
/* Single-file tools: shared loading logic                             */
/* ------------------------------------------------------------------ */

async function loadSingleFile(files, statusEl) {
  const file = files[0];
  if (files.length > 1) {
    setStatus(statusEl, "error", "This tool works on one PDF at a time — using the first file only.");
  }
  if (!isPdfFile(file)) {
    setStatus(statusEl, "error", `“${file.name}” doesn’t look like a PDF.`);
    return null;
  }
  setStatus(statusEl, "busy", `Reading ${file.name}…`);
  try {
    const bytes = await readFileBytes(file);
    const pages = await ops.pageCount(bytes, file.name);
    setStatus(statusEl, null, "");
    return { name: file.name, size: file.size, bytes, pages };
  } catch (err) {
    setStatus(statusEl, "error", err.message);
    return null;
  }
}

function renderFileChip(chipEl, doc, onClear) {
  chipEl.hidden = false;
  chipEl.innerHTML = "";
  const label = document.createElement("span");
  label.className = "chip-label";
  label.innerHTML = `<strong></strong> · ${plural(doc.pages, "page")} · ${fmtSize(doc.size)}`;
  label.querySelector("strong").textContent = doc.name;
  const clear = document.createElement("button");
  clear.type = "button";
  clear.className = "chip-clear";
  clear.setAttribute("aria-label", `Remove ${doc.name}`);
  clear.textContent = "✕";
  clear.addEventListener("click", onClear);
  chipEl.appendChild(label);
  chipEl.appendChild(clear);
}

/* ------------------------------------------------------------------ */
/* Tabs                                                                */
/* ------------------------------------------------------------------ */

const tabs = Array.from(document.querySelectorAll('[role="tab"]'));
function selectTab(tab) {
  for (const t of tabs) {
    const selected = t === tab;
    t.setAttribute("aria-selected", String(selected));
    t.tabIndex = selected ? 0 : -1;
    $(t.getAttribute("aria-controls")).hidden = !selected;
  }
  tab.focus();
}
tabs.forEach((tab, i) => {
  tab.addEventListener("click", () => selectTab(tab));
  tab.addEventListener("keydown", (event) => {
    let target = null;
    if (event.key === "ArrowRight") target = tabs[(i + 1) % tabs.length];
    else if (event.key === "ArrowLeft") target = tabs[(i - 1 + tabs.length) % tabs.length];
    else if (event.key === "Home") target = tabs[0];
    else if (event.key === "End") target = tabs[tabs.length - 1];
    if (target) {
      event.preventDefault();
      selectTab(target);
    }
  });
});

/* ------------------------------------------------------------------ */
/* Merge                                                               */
/* ------------------------------------------------------------------ */

const mergeState = { files: [] };

function renderMergeList() {
  const list = $("merge-list");
  list.innerHTML = "";
  mergeState.files.forEach((doc, i) => {
    const li = document.createElement("li");
    li.className = "file-row";
    const info = document.createElement("span");
    info.className = "file-info";
    info.innerHTML = `<strong></strong> <span class="muted">${plural(doc.pages, "page")} · ${fmtSize(doc.size)}</span>`;
    info.querySelector("strong").textContent = `${i + 1}. ${doc.name}`;
    const controls = document.createElement("span");
    controls.className = "file-controls";
    const mkBtn = (label, ariaLabel, disabled, onClick) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "icon-btn";
      b.textContent = label;
      b.setAttribute("aria-label", ariaLabel);
      b.disabled = disabled;
      b.addEventListener("click", onClick);
      return b;
    };
    controls.appendChild(
      mkBtn("↑", `Move ${doc.name} up`, i === 0, () => {
        [mergeState.files[i - 1], mergeState.files[i]] = [mergeState.files[i], mergeState.files[i - 1]];
        renderMergeList();
      })
    );
    controls.appendChild(
      mkBtn("↓", `Move ${doc.name} down`, i === mergeState.files.length - 1, () => {
        [mergeState.files[i + 1], mergeState.files[i]] = [mergeState.files[i], mergeState.files[i + 1]];
        renderMergeList();
      })
    );
    controls.appendChild(
      mkBtn("✕", `Remove ${doc.name}`, false, () => {
        mergeState.files.splice(i, 1);
        renderMergeList();
      })
    );
    li.appendChild(info);
    li.appendChild(controls);
    list.appendChild(li);
  });

  const n = mergeState.files.length;
  $("merge-run").disabled = n < 2;
  $("merge-count").textContent = n ? `${plural(n, "file")}` : "";
  $("merge-clear").hidden = n === 0;
  if (n === 1) {
    setStatus($("merge-status"), null, "Add at least one more PDF to merge.");
  } else if (n === 0) {
    setStatus($("merge-status"), null, "");
  } else {
    const total = mergeState.files.reduce((sum, d) => sum + d.pages, 0);
    setStatus($("merge-status"), null, `Ready: ${plural(n, "file")}, ${plural(total, "page")} total.`);
  }
}

wireDropzone($("merge-drop"), $("merge-input"), async (files) => {
  const statusEl = $("merge-status");
  const pdfs = files.filter(isPdfFile);
  if (!pdfs.length) {
    setStatus(statusEl, "error", "None of those files look like PDFs.");
    return;
  }
  setStatus(statusEl, "busy", `Reading ${plural(pdfs.length, "file")}…`);
  const errors = [];
  for (const file of pdfs) {
    try {
      const bytes = await readFileBytes(file);
      const pages = await ops.pageCount(bytes, file.name);
      mergeState.files.push({ name: file.name, size: file.size, bytes, pages });
    } catch (err) {
      errors.push(err.message);
    }
  }
  renderMergeList();
  if (errors.length) setStatus(statusEl, "error", errors.join(" — "));
});

$("merge-clear").addEventListener("click", () => {
  mergeState.files = [];
  $("merge-results").innerHTML = "";
  renderMergeList();
});

$("merge-run").addEventListener("click", async () => {
  const statusEl = $("merge-status");
  const btn = $("merge-run");
  btn.disabled = true;
  setStatus(statusEl, "busy", "Merging…");
  try {
    const { bytes, pages } = await ops.merge(mergeState.files);
    renderResults(
      $("merge-results"),
      [{ name: "merged.pdf", bytes }],
      `Done — ${mergeState.files.length} files merged into one ${pages}-page PDF.`
    );
    setStatus(statusEl, "ok", "Merge complete. Your download is ready below.");
  } catch (err) {
    setStatus(statusEl, "error", err.message);
  } finally {
    btn.disabled = mergeState.files.length < 2;
  }
});

/* ------------------------------------------------------------------ */
/* Split                                                               */
/* ------------------------------------------------------------------ */

const splitState = { doc: null };

function splitMode() {
  const value = document.querySelector('input[name="split-mode"]:checked').value;
  if (value === "ranges") return { ranges: $("split-ranges").value };
  if (value === "every") return { every: parseInt($("split-every").value, 10) };
  return { all: true };
}

function validateSplit() {
  const errorEl = $("split-error");
  const run = $("split-run");
  if (!splitState.doc) {
    run.disabled = true;
    errorEl.hidden = true;
    return;
  }
  const mode = splitMode();
  let error = null;
  if (mode.ranges !== undefined) {
    error = selectorError(mode.ranges, splitState.doc.pages, { label: "pages to extract" });
  } else if (mode.every !== undefined) {
    if (!Number.isInteger(mode.every) || mode.every < 1) {
      error = "Pages per chunk must be a positive whole number.";
    }
  }
  errorEl.textContent = error || "";
  errorEl.hidden = !error;
  run.disabled = Boolean(error);
}

wireDropzone($("split-drop"), $("split-input"), async (files) => {
  const doc = await loadSingleFile(files, $("split-status"));
  if (!doc) return;
  splitState.doc = doc;
  renderFileChip($("split-file"), doc, () => {
    splitState.doc = null;
    $("split-file").hidden = true;
    $("split-options").disabled = true;
    $("split-results").innerHTML = "";
    validateSplit();
  });
  $("split-options").disabled = false;
  $("split-every").max = doc.pages;
  validateSplit();
});

for (const el of document.querySelectorAll('input[name="split-mode"], #split-ranges, #split-every')) {
  el.addEventListener("input", validateSplit);
}
$("split-ranges").addEventListener("focus", () => {
  document.querySelector('input[name="split-mode"][value="ranges"]').checked = true;
  validateSplit();
});
$("split-every").addEventListener("focus", () => {
  document.querySelector('input[name="split-mode"][value="every"]').checked = true;
  validateSplit();
});

$("split-run").addEventListener("click", async () => {
  const statusEl = $("split-status");
  const btn = $("split-run");
  btn.disabled = true;
  setStatus(statusEl, "busy", "Splitting…");
  try {
    const outputs = await ops.split(splitState.doc.bytes, splitState.doc.name, splitMode());
    renderResults(
      $("split-results"),
      outputs,
      `Done — ${plural(splitState.doc.pages, "page")} split into ${plural(outputs.length, "file")}.`
    );
    setStatus(statusEl, "ok", `Split complete: ${plural(outputs.length, "file")} ready below.`);
  } catch (err) {
    setStatus(statusEl, "error", err.message);
  } finally {
    btn.disabled = false;
    validateSplit();
  }
});

/* ------------------------------------------------------------------ */
/* Rotate                                                              */
/* ------------------------------------------------------------------ */

const rotateState = { doc: null };

function validateRotate() {
  const errorEl = $("rotate-error");
  const run = $("rotate-run");
  if (!rotateState.doc) {
    run.disabled = true;
    errorEl.hidden = true;
    return;
  }
  const error = selectorError($("rotate-pages").value, rotateState.doc.pages, {
    required: false,
  });
  errorEl.textContent = error || "";
  errorEl.hidden = !error;
  run.disabled = Boolean(error);
}

wireDropzone($("rotate-drop"), $("rotate-input"), async (files) => {
  const doc = await loadSingleFile(files, $("rotate-status"));
  if (!doc) return;
  rotateState.doc = doc;
  renderFileChip($("rotate-file"), doc, () => {
    rotateState.doc = null;
    $("rotate-file").hidden = true;
    $("rotate-options").disabled = true;
    $("rotate-results").innerHTML = "";
    validateRotate();
  });
  $("rotate-options").disabled = false;
  validateRotate();
});

$("rotate-pages").addEventListener("input", validateRotate);

$("rotate-run").addEventListener("click", async () => {
  const statusEl = $("rotate-status");
  const btn = $("rotate-run");
  const deg = parseInt(document.querySelector('input[name="rotate-deg"]:checked').value, 10);
  btn.disabled = true;
  setStatus(statusEl, "busy", "Rotating…");
  try {
    const { bytes, rotated } = await ops.rotate(
      rotateState.doc.bytes,
      rotateState.doc.name,
      $("rotate-pages").value,
      deg
    );
    const stem = rotateState.doc.name.replace(/\.pdf$/i, "");
    renderResults(
      $("rotate-results"),
      [{ name: `${stem}_rotated.pdf`, bytes }],
      `Done — rotated ${plural(rotated, "page")}.`
    );
    setStatus(statusEl, "ok", "Rotation complete. Your download is ready below.");
  } catch (err) {
    setStatus(statusEl, "error", err.message);
  } finally {
    btn.disabled = false;
    validateRotate();
  }
});

/* ------------------------------------------------------------------ */
/* Organize (extract / delete / reorder)                               */
/* ------------------------------------------------------------------ */

const organizeState = { doc: null };
const ORGANIZE_COPY = {
  extract: { label: "Pages to keep", placeholder: "e.g. 2-4,7", verb: "Keep pages" },
  delete: { label: "Pages to delete", placeholder: "e.g. 3 or 1,5-6", verb: "Delete pages" },
  reorder: { label: "New page order", placeholder: "e.g. 3,1,2 — or 5-1 to reverse", verb: "Reorder pages" },
};

function organizeMode() {
  return document.querySelector('input[name="organize-mode"]:checked').value;
}

function updateOrganizeCopy() {
  const copy = ORGANIZE_COPY[organizeMode()];
  $("organize-pages-label").textContent = copy.label;
  $("organize-pages").placeholder = copy.placeholder;
  $("organize-run").textContent = copy.verb;
}

function validateOrganize() {
  const errorEl = $("organize-error");
  const run = $("organize-run");
  if (!organizeState.doc) {
    run.disabled = true;
    errorEl.hidden = true;
    return;
  }
  const error = selectorError($("organize-pages").value, organizeState.doc.pages, {
    label: ORGANIZE_COPY[organizeMode()].label.toLowerCase(),
  });
  errorEl.textContent = error || "";
  errorEl.hidden = !error;
  run.disabled = Boolean(error);
}

wireDropzone($("organize-drop"), $("organize-input"), async (files) => {
  const doc = await loadSingleFile(files, $("organize-status"));
  if (!doc) return;
  organizeState.doc = doc;
  renderFileChip($("organize-file"), doc, () => {
    organizeState.doc = null;
    $("organize-file").hidden = true;
    $("organize-options").disabled = true;
    $("organize-results").innerHTML = "";
    validateOrganize();
  });
  $("organize-options").disabled = false;
  validateOrganize();
});

for (const el of document.querySelectorAll('input[name="organize-mode"]')) {
  el.addEventListener("change", () => {
    updateOrganizeCopy();
    validateOrganize();
  });
}
$("organize-pages").addEventListener("input", validateOrganize);
updateOrganizeCopy();

$("organize-run").addEventListener("click", async () => {
  const statusEl = $("organize-status");
  const btn = $("organize-run");
  const mode = organizeMode();
  const selector = $("organize-pages").value;
  const doc = organizeState.doc;
  btn.disabled = true;
  setStatus(statusEl, "busy", "Working…");
  try {
    let result;
    let suffix;
    if (mode === "extract") {
      result = await ops.extractPages(doc.bytes, doc.name, selector);
      suffix = "extracted";
    } else if (mode === "delete") {
      result = await ops.deletePages(doc.bytes, doc.name, selector);
      suffix = "trimmed";
    } else {
      result = await ops.reorder(doc.bytes, doc.name, selector);
      suffix = "reordered";
    }
    const stem = doc.name.replace(/\.pdf$/i, "");
    renderResults(
      $("organize-results"),
      [{ name: `${stem}_${suffix}.pdf`, bytes: result.bytes }],
      `Done — the new document has ${plural(result.pages, "page")}.`
    );
    setStatus(statusEl, "ok", "All set. Your download is ready below.");
  } catch (err) {
    setStatus(statusEl, "error", err.message);
  } finally {
    btn.disabled = false;
    validateOrganize();
  }
});

/* ------------------------------------------------------------------ */
/* Inspect                                                             */
/* ------------------------------------------------------------------ */

wireDropzone($("inspect-drop"), $("inspect-input"), async (files) => {
  const statusEl = $("inspect-status");
  const resultsEl = $("inspect-results");
  const file = files[0];
  if (!isPdfFile(file)) {
    setStatus(statusEl, "error", `“${file.name}” doesn’t look like a PDF.`);
    return;
  }
  resultsEl.innerHTML = "";
  setStatus(statusEl, "busy", `Reading ${file.name}…`);
  try {
    const bytes = await readFileBytes(file);
    const info = await ops.inspect(bytes, file.name);
    setStatus(statusEl, null, "");

    const card = document.createElement("div");
    card.className = "info-card";
    const title = document.createElement("h3");
    title.textContent = file.name;
    card.appendChild(title);

    const dl = document.createElement("dl");
    const addRow = (dt, dd) => {
      const dtEl = document.createElement("dt");
      dtEl.textContent = dt;
      const ddEl = document.createElement("dd");
      ddEl.textContent = dd;
      dl.appendChild(dtEl);
      dl.appendChild(ddEl);
    };
    addRow("File size", fmtSize(file.size));
    addRow("Pages", String(info.pages));

    const uniqueSizes = [...new Set(info.pageSizes.map(([w, h]) => `${w} × ${h} pt`))];
    addRow(
      "Page size",
      uniqueSizes.length === 1 ? uniqueSizes[0] : `${uniqueSizes.length} different sizes (first: ${uniqueSizes[0]})`
    );
    for (const [key, value] of Object.entries(info.metadata)) {
      addRow(key, value);
    }
    card.appendChild(dl);
    resultsEl.appendChild(card);
  } catch (err) {
    setStatus(statusEl, "error", err.message);
  }
});

/* ------------------------------------------------------------------ */
/* Share                                                               */
/* ------------------------------------------------------------------ */

$("share-btn").addEventListener("click", async () => {
  const shareData = {
    title: "PDF Toolkit",
    text: "Merge, split & rotate PDFs privately in your browser — no uploads.",
    url: "https://smolkapps.github.io/pdf-toolkit/",
  };
  if (navigator.share) {
    try {
      await navigator.share(shareData);
      return;
    } catch (err) {
      if (err.name === "AbortError") return; // user closed the share sheet
    }
  }
  try {
    await navigator.clipboard.writeText(shareData.url);
    showToast("Link copied to clipboard");
  } catch {
    showToast(shareData.url);
  }
});

/* ------------------------------------------------------------------ */
/* Offline support                                                     */
/* ------------------------------------------------------------------ */

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("sw.js").catch(() => {
      /* offline caching is progressive enhancement — the app works without it */
    });
  });
}
