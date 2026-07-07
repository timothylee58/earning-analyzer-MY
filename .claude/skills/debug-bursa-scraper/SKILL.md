---
name: debug-bursa-scraper
description: Diagnose and fix the Bursa Malaysia scraper (apps/scraper/bursa.py) when announcement listing, row parsing, PDF resolution, or PDF extraction breaks — usually because Bursa's markup or JSON shifted. Uses a capture-once, iterate-offline workflow so debugging never hammers bursamalaysia.com.
---

# Debug the Bursa scraper (capture once, iterate offline)

Bursa's frontend endpoints are undocumented and shift shape occasionally.
The scraper is written defensively (`parse_row` degrades to skip), so
breakage usually looks like "0 announcements ingested" rather than a
traceback. Never debug against the live site in a loop (CLAUDE.md M9).

## Step 1 — Localize the failure

The pipeline has four stages; test them in order and stop at the first
broken one:

1. **Listing** — `bursa.fetch_announcements()` returns rows?
2. **Row parsing** — `bursa.parse_row(row)` yields ann_id/url/title?
3. **PDF resolution** — `bursa.resolve_pdf_url(ann_url)` finds the PDF link?
4. **Extraction** — `pdf_extract.extract_narrative(path)` yields prose?

## Step 2 — Capture live responses ONCE to disk

One request per stage, saved to files; all further iteration is offline:

```bash
mkdir -p /tmp/bursa-debug
python3 - <<'EOF'
import requests
from apps.scraper.bursa import LIST_URL, HEADERS, QUARTERLY_CATEGORY
r = requests.get(LIST_URL, params={"ann_type": "company", "cat": QUARTERLY_CATEGORY,
                                   "page": 1, "per_page": 5},
                 headers=HEADERS, timeout=30)
print("status:", r.status_code, "content-type:", r.headers.get("content-type"))
open("/tmp/bursa-debug/listing.raw", "wb").write(r.content)
EOF
```

(Run inside `python3 manage.py shell` or with `DJANGO_SETTINGS_MODULE` set.)
Then, if stage 3 is suspect, fetch ONE announcement detail page the same
way into `/tmp/bursa-debug/detail.html`. That's the entire live budget:
two requests.

Note: this sandbox's proxy may block bursamalaysia.com entirely. If the
capture request itself fails with a connection/proxy error, you cannot
debug the live shape here — fix what's provable from existing fixtures,
and state in the PR that live capture must be run by the user (paste them
the capture snippet above).

## Step 3 — Diagnose against the captured file

Common shifts and their fixes:

| Symptom in capture | Likely shift | Fix location |
|---|---|---|
| HTML page instead of JSON | Endpoint now requires `X-Requested-With: XMLHttpRequest` or similar header | `HEADERS` in `bursa.py` |
| JSON but `data` key renamed/nested | Payload restructure | `fetch_announcements` return line |
| Rows are dicts now, not positional lists | API v-next | `parse_row` — extend the `isinstance(row, dict)` branch to normalise keys |
| Row list order changed / extra column | Frontend table change | Index constants in `parse_row` (`row[1], row[2], row[3]`) |
| `ann_id=` regex misses | URL format change | `ann_id_m` regex in `parse_row` |
| PDF href pattern misses | Attachment path changed from `/misc/V3/` | `_ATTACHMENT_RE` in `bursa.py` |
| Prose extraction empty on valid PDF | Report is scanned/image-based | Out of scope — log and skip; OCR is a new dependency (escalate, CLAUDE.md rule 2) |

## Step 4 — Turn the capture into a permanent fixture test

Whatever shape you found, freeze a minimal sample of it (one row, one
href snippet — strip anything bulky) directly into
`apps/scraper/tests.py` as a new test case alongside `ParseRowTests`.
The rule: **every markup shift that broke us once gets a fixture test so
it can never break silently again.** Do not commit the raw capture files.

## Step 5 — Verify

1. `python3 manage.py test apps.scraper` — new fixture test + old ones pass
   (old fixtures stay: `parse_row` must handle BOTH shapes, old and new,
   because defensive parsing is the convention).
2. One (1) live confirmation only:
   `python3 manage.py scrape_bursa --pages 1` — expect
   `Ingested N new announcements` with N > 0.
3. Confirm politeness intact: `RATE_LIMIT_SECONDS` and the identifying
   `User-Agent` are unchanged in the diff. If the fix seems to need faster
   or broader crawling — stop and ask (CLAUDE.md escalation rule 3).
