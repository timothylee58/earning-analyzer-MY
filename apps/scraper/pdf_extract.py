"""Extract analyzable text from Bursa quarterly report PDFs.

Quarterly reports are mostly tables; the sentiment signal lives in the
narrative sections (Review of Performance, Prospects, B-notes commentary).
We extract all page text and keep prose-like lines only.
"""

import re
from pathlib import Path

_MIN_WORDS = 4
_NUMERIC_RATIO_MAX = 0.5
_WORD = re.compile(r"[A-Za-z']+")
_NUM = re.compile(r"[\d,.()%]+")


def extract_text(pdf_path: Path | str) -> str:
    import pdfplumber  # heavy import kept local

    parts = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            parts.append(text)
    return "\n".join(parts)


def keep_prose(raw_text: str) -> str:
    """Drop table rows / headers, keep narrative lines worth scoring."""
    lines = []
    for line in raw_text.splitlines():
        line = line.strip()
        words = _WORD.findall(line)
        if len(words) < _MIN_WORDS:
            continue
        numeric = _NUM.findall(line)
        if len(numeric) / max(1, len(words) + len(numeric)) > _NUMERIC_RATIO_MAX:
            continue
        lines.append(line)
    return "\n".join(lines)


def extract_narrative(pdf_path: Path | str) -> str:
    return keep_prose(extract_text(pdf_path))
