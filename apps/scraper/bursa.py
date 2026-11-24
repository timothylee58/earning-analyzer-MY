"""Bursa Malaysia quarterly report scraper.

Pulls company announcements filtered to quarterly reports (category FA) from
the Bursa Malaysia announcements endpoint, resolves the attached PDF, and
downloads it for text extraction.

Bursa serves announcement listings as JSON to its own frontend at
/market_information/announcements/company_announcement — we use the same
endpoint politely (identify ourselves, rate-limit, small pages).
"""

import logging
import re
import time
from pathlib import Path

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

BASE = "https://www.bursamalaysia.com"
LIST_URL = f"{BASE}/market_information/announcements/company_announcement"
HEADERS = {
    "User-Agent": "earnings-analyzer-my/0.1 (research; contact via GitHub)",
    "Accept": "application/json",
}
QUARTERLY_CATEGORY = "FA"  # Financial Results
RATE_LIMIT_SECONDS = 1.0

_ATTACHMENT_RE = re.compile(r"href=\"(/misc/V3/[^\"]+\.pdf)\"", re.IGNORECASE)


class BursaAccessError(requests.RequestException):
    """The remote site requires interactive or approved access."""


def _check_response(resp):
    if resp.status_code == 403 or resp.headers.get("cf-mitigated") == "challenge":
        raise BursaAccessError(
            "Bursa denied automated access (HTTP 403/challenge). "
            "Download a report using your browser or the company's investor-relations "
            "site, then run: python manage.py analyze_pdf /path/to/report.pdf --offline. "
            "Live scraping requires permitted automated access."
        )
    resp.raise_for_status()


def fetch_announcements(page: int = 1, per_page: int = 20) -> list[dict]:
    """Return raw announcement rows for quarterly reports (newest first)."""
    params = {
        "ann_type": "company",
        "cat": QUARTERLY_CATEGORY,
        "page": page,
        "per_page": per_page,
    }
    resp = requests.get(LIST_URL, params=params, headers=HEADERS, timeout=30)
    _check_response(resp)
    try:
        payload = resp.json()
    except ValueError as exc:
        raise BursaAccessError("Bursa returned HTML/non-JSON instead of an announcement listing.") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise BursaAccessError("Bursa listing schema changed: expected a data list.")
    return payload["data"]


def parse_row(row: list | dict) -> dict:
    """Normalise one announcement row to {ann_id, date, company, title, url}.

    The endpoint returns rows as positional lists of HTML fragments:
    [seq, date_html, company_html, title_html]. Keep parsing defensive —
    the markup shifts occasionally.
    """
    if isinstance(row, dict):
        return row
    date_html, company_html, title_html = row[1], row[2], row[3]
    link = re.search(r"href=\"([^\"]+)\"", title_html)
    ann_url = BASE + link.group(1) if link else ""
    ann_id_m = re.search(r"ann_id=(\d+)", ann_url)
    return {
        "ann_id": ann_id_m.group(1) if ann_id_m else ann_url,
        "date": _strip_tags(date_html),
        "company": _strip_tags(company_html),
        "title": _strip_tags(title_html),
        "url": ann_url,
    }


def resolve_pdf_url(announcement_url: str) -> str | None:
    """Fetch the announcement detail page and find the attached PDF."""
    resp = requests.get(announcement_url, headers=HEADERS, timeout=30)
    _check_response(resp)
    m = _ATTACHMENT_RE.search(resp.text)
    return BASE + m.group(1) if m else None


def download_pdf(pdf_url: str, dest_dir: Path | None = None) -> Path:
    dest_dir = dest_dir or settings.PDF_DIR
    dest_dir.mkdir(parents=True, exist_ok=True)
    filename = pdf_url.rsplit("/", 1)[-1]
    dest = dest_dir / filename
    if dest.exists():
        return dest
    resp = requests.get(pdf_url, headers=HEADERS, timeout=60)
    _check_response(resp)
    if not resp.content.startswith(b"%PDF-"):
        raise BursaAccessError("Bursa download was not a PDF; nothing was saved.")
    dest.write_bytes(resp.content)
    time.sleep(RATE_LIMIT_SECONDS)
    return dest


def _strip_tags(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html).strip()
