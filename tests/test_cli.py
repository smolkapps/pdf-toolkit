"""End-to-end tests that drive the real argparse CLI entry point.

These call ``pdftoolkit.cli.main(argv)`` with argument lists exactly as the
console script would receive them, asserting on exit codes, produced files,
and stdout/stderr — the layer where arg marshalling actually happens.
"""

from __future__ import annotations

import pytest
from pypdf import PdfReader

from pdftoolkit.cli import main


def test_cli_merge(make_pdf, tmp_path, capsys):
    a = make_pdf("a.pdf", 2)
    b = make_pdf("b.pdf", 3)
    out = str(tmp_path / "out.pdf")

    rc = main(["merge", a, b, "-o", out])

    assert rc == 0
    assert len(PdfReader(out).pages) == 5
    assert "5 pages" in capsys.readouterr().out


def test_cli_split_every(make_pdf, tmp_path, capsys):
    src = make_pdf("doc.pdf", 5)
    outdir = str(tmp_path / "out")
    rc = main(["split", src, "--every", "2", "--outdir", outdir])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Wrote 3 file(s)" in out


def test_cli_info(make_pdf, capsys):
    src = make_pdf("doc.pdf", 4)
    rc = main(["info", src])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Pages:       4" in out
    assert "Encrypted:   no" in out


def test_cli_text(make_pdf, capsys):
    src = make_pdf("doc.pdf", 2)
    rc = main(["text", src])
    assert rc == 0
    out = capsys.readouterr().out
    assert "PAGE 1" in out
    assert "PAGE 2" in out


def test_cli_rotate(make_pdf, tmp_path, capsys):
    src = make_pdf("doc.pdf", 2)
    out = str(tmp_path / "rot.pdf")
    rc = main(["rotate", src, "--pages", "1", "--degrees", "90", "-o", out])
    assert rc == 0
    reader = PdfReader(out)
    assert int(reader.pages[0].get("/Rotate", 0)) == 90


def test_cli_extract(make_pdf, tmp_path):
    src = make_pdf("doc.pdf", 5)
    out = str(tmp_path / "ex.pdf")
    rc = main(["extract", src, "--pages", "2-3", "-o", out])
    assert rc == 0
    assert len(PdfReader(out).pages) == 2


def test_cli_compress(make_pdf, tmp_path, capsys):
    src = make_pdf("doc.pdf", 6, extra_filler=True)
    out = str(tmp_path / "c.pdf")
    rc = main(["compress", src, "-o", out])
    assert rc == 0
    assert "Compressed" in capsys.readouterr().out


def test_cli_missing_file_exits_2(tmp_path, capsys):
    rc = main(["info", str(tmp_path / "nope.pdf")])
    assert rc == 2
    assert "error:" in capsys.readouterr().err


def test_cli_bad_pages_exits_2(make_pdf, tmp_path, capsys):
    src = make_pdf("doc.pdf", 3)
    out = str(tmp_path / "o.pdf")
    rc = main(["extract", src, "--pages", "9", "-o", out])
    assert rc == 2
    assert "error:" in capsys.readouterr().err


def test_cli_no_command_exits_nonzero(capsys):
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code != 0
