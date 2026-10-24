#!/usr/bin/env python3
"""Extract a PDF into a page-marked plain-text file for chunked deep reading.

Why this exists:
    Deep reading must proceed "one part at a time". Re-reading a whole PDF on
    every turn is slow, token-expensive and prone to truncation. Extracting the
    PDF once into a stable text file with page markers lets later turns read
    only the page range that belongs to the current section.

Usage:
    python extract_pdf_text.py <input.pdf> [output.txt]

Output format:
    <<<PAGE 1>>>
    ...page 1 text...

    <<<PAGE 2>>>
    ...page 2 text...

If no output path is given, writes <input stem>.pages.txt next to the PDF.
Prints a short JSON summary to stdout so the caller can plan the reading.
"""

import json
import os
import re
import sys


def _load_reader(path):
    """Return a (page_count, get_text(page_index)) callable pair, or raise."""
    try:
        from pypdf import PdfReader  # pypdf >= 3
    except ImportError:
        try:
            from PyPDF2 import PdfReader  # legacy fallback
        except ImportError:
            raise SystemExit(
                "No PDF library found. Install one, e.g.:\n"
                "  pip install pypdf"
            )
    reader = PdfReader(path)
    return reader


def clean(text):
    """Normalise whitespace and repair common PDF extraction artefacts."""
    if not text:
        return ""
    # Join words split across a line break by hyphenation: "atten- tion" -> "attention"
    text = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", text)
    # Collapse intra-line runs of spaces
    text = re.sub(r"[ \t]{2,}", " ", text)
    # Drop reference-style page furniture
    text = re.sub(r"\n\s*\d{1,4}\s*\n", "\n", text)
    # Collapse 3+ blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)

    pdf_path = os.path.abspath(sys.argv[1])
    if not os.path.isfile(pdf_path):
        raise SystemExit(f"File not found: {pdf_path}")

    if len(sys.argv) >= 3:
        out_path = os.path.abspath(sys.argv[2])
    else:
        stem = os.path.splitext(pdf_path)[0]
        out_path = stem + ".pages.txt"

    reader = _load_reader(pdf_path)

    chunks = []
    page_chars = []
    for i, page in enumerate(reader.pages, start=1):
        try:
            raw = page.extract_text() or ""
        except Exception as exc:  # a single bad page must not kill the run
            raw = f"[extraction failed on page {i}: {exc}]"
        body = clean(raw)
        page_chars.append(len(body))
        chunks.append(f"<<<PAGE {i}>>>\n{body}\n")

    full = "\n".join(chunks)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(full)

    summary = {
        "source": pdf_path,
        "output": out_path,
        "pages": len(chunks),
        "chars": len(full),
        "empty_pages": [i + 1 for i, n in enumerate(page_chars) if n < 40],
        "note": (
            "Pages listed in empty_pages are likely scanned images. "
            "Read the PDF directly (vision) for those pages."
        ),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
