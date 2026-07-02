# pdf-toolkit

A complete, **offline** command-line toolkit for manipulating PDF files. No
network access, no cloud services, no API keys — every operation runs locally
against your files.

Built on [`pypdf`](https://pypdf.readthedocs.io/) for structural page
operations and [`pikepdf`](https://pikepdf.readthedocs.io/) (libqpdf) for
robust metadata inspection and compression.

## Install

```bash
pip install .
# or, for development with the test extras:
pip install -e ".[test]"
```

This installs a single console script: **`pdftoolkit`**.

## Commands

| Command    | What it does                                                        |
|------------|---------------------------------------------------------------------|
| `merge`    | Concatenate several PDFs into one                                   |
| `split`    | Split one PDF into many (by ranges, by every-N pages, or per-page)  |
| `rotate`   | Rotate selected pages by a multiple of 90 degrees                  |
| `extract`  | Keep only a subset of pages                                        |
| `delete`   | Remove a subset of pages                                           |
| `reorder`  | Rearrange pages into a new order                                   |
| `text`     | Extract plain text, one block per page                            |
| `extract-images` | Export embedded raster images (XObject + inline) to files   |
| `info`     | Show page count, page size, PDF version, metadata, encryption      |
| `compress` | Re-save with object streams + stream compression (best effort)     |

### Page selectors

`--pages` / `--ranges` / `--order` all accept the same **1-based, inclusive**
syntax:

```
3            a single page
2-4          an inclusive range (pages 2, 3, 4)
1,3,5        a list
1-3,5,7-8    any combination
4-2          a descending range (4, 3, 2) — handy for reverse/reorder
```

## Examples

```bash
# Merge three files in order
pdftoolkit merge cover.pdf body.pdf appendix.pdf -o book.pdf

# Pull pages 1-3 and 5 into a single new file
pdftoolkit split report.pdf --ranges "1-3,5" --outdir out/

# Burst into chunks of 10 pages each
pdftoolkit split big.pdf --every 10 --outdir chunks/

# One file per page
pdftoolkit split slides.pdf --all --outdir pages/

# Rotate pages 1 and 2 a quarter-turn clockwise
pdftoolkit rotate scan.pdf --pages 1,2 --degrees 90 -o fixed.pdf

# Extract / delete / reorder
pdftoolkit extract report.pdf --pages 2-4 -o excerpt.pdf
pdftoolkit delete  report.pdf --pages 3   -o trimmed.pdf
pdftoolkit reorder report.pdf --order 3,1,2 -o shuffled.pdf

# Inspect and read
pdftoolkit info report.pdf
pdftoolkit text report.pdf

# Export every embedded raster image (skipping tiny spacer pixels)
pdftoolkit extract-images report.pdf --outdir images/ --min-size 8

# Shrink (honest about results — see below)
pdftoolkit compress report.pdf -o smaller.pdf
```

## A note on `compress`

`compress` is **best effort**. It re-saves the file with qpdf's object
streams enabled and recompresses content streams. For text-heavy or naively
written PDFs this can meaningfully reduce size; for PDFs whose bulk is
already-compressed images (most scans) it saves little or nothing. The tool
reports the real before/after byte counts and **guarantees the output is never
larger than the input** — if qpdf's re-save would grow the file, the original
bytes are kept. It does not downsample images or strip content, so it will not
claim dramatic gains it cannot deliver.

## A note on `extract-images`

`extract-images` exports the raster images stored in a PDF: image XObjects
(including those nested inside form XObjects) and inline `BI`/`ID`/`EI` images,
which are promoted to XObjects before extraction. Each distinct image object is
written once even when reused across pages, and files keep their stored
encoding where possible (`.jpg` for DCT/JPEG, `.png` otherwise).

Limitations to be aware of:

- **Soft masks / transparency are not composited.** An image's alpha channel
  is a separate `/SMask` object; the extracted file is the base colour image
  **without** transparency applied. Images that relied on an SMask will look
  opaque.
- **Vector graphics are not images** and are not exported — this tool extracts
  raster images only, not drawings or text.
- **Undecodable images are skipped, not fatal.** An image using a codec qpdf
  and Pillow cannot decode (e.g. JBIG2 without `jbig2dec`, or a truncated
  stream) is counted and reported (`note: skipped N image(s)…`) so one bad
  image in a scanned PDF does not abort the whole run.

## Behaviour and exit codes

- Bad input (missing file, unreadable file, password-protected PDF, an
  out-of-range or malformed page selector) prints `error: <message>` to
  stderr and exits with code **2**.
- Encrypted PDFs that require a password are rejected with a clear message;
  this toolkit does not accept passwords. Files encrypted with an *empty* user
  password (copy-protection only) are opened transparently.
- Successful runs exit **0** and print a short summary to stdout.

## Development

```bash
pip install -e ".[test]"
pytest -q
```

Tests build their own known-content PDFs with `reportlab` (see
`tests/make_fixtures.py`), so no binary fixtures are checked in. Each fixture
page carries a detectable `PAGE N` marker, which the tests read back to verify
that page **content and order** — not merely page counts — survive every
operation.

## License

MIT — see [LICENSE](LICENSE).
