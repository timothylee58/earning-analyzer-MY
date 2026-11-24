# Earnings Analyzer Malaysia

**FinBERT + XLM-RoBERTa dual pipeline for Manglish/BM earnings calls.**

Bursa Malaysia quarterly PDF scraper with a dual NLP pipeline: FinBERT scores
formal English, XLM-RoBERTa handles Manglish / Bahasa Malaysia code-switching.
Standard FinBERT is trained on US transcripts and misses the Manglish/BM
sentiment signals critical to Bursa earnings calls — this project closes that
linguistic gap.

**Stakeholders:** Malaysian retail investors, Bursa quant analysts.

## Architecture

```
Bursa announcements ──▶ PDF scraper ──▶ prose extraction (pdfplumber)
                                              │
                                    per-sentence language router
                                     ┌────────┴────────┐
                              formal English      Manglish / BM
                                     │                 │
                                 FinBERT          XLM-RoBERTa
                              (ProsusAI/finbert)  (cardiffnlp/twitter-xlm-
                                     │             roberta-base-sentiment)
                                     └────────┬────────┘
                             confidence-weighted ensemble vote
                                              │
                          ┌───────────────────┼───────────────────┐
                    doc sentiment       FLS extraction      feature vector
                                                                  │
                                                     price direction model
                                                     (logistic regression)
                                                                  │
                                                         event backtest
```

Two services:

- **Django** (`config/`, `apps/`) — scraper, NLP pipeline, signals, REST API.
- **Spring Boot gateway** (`gateway/`) — thin API gateway in front of the
  Django service for auth/rate-limiting concerns (port 8081).

Models are served via the **Hugging Face Inference API** (no GPU needed);
without an `HF_API_TOKEN` the pipeline falls back to a deterministic lexicon
scorer so everything stays runnable and testable offline.

## Core features

| Feature | Where |
|---|---|
| Bursa quarterly PDF scraper | `apps/scraper/bursa.py`, `manage.py scrape_bursa` |
| Prose extraction from table-heavy PDFs | `apps/scraper/pdf_extract.py` |
| Per-sentence language routing (Layer 1) | `apps/nlp/router.py`, `apps/nlp/lexicon.py` |
| FinBERT (formal EN) + XLM-R (Manglish/BM) clients | `apps/nlp/hf_client.py` |
| Confidence-weighted ensemble vote (Layer 2) | `apps/nlp/ensemble.py` |
| Forward-looking statement extraction | `apps/signals/fls.py` |
| Price direction model (numpy logistic regression) | `apps/signals/direction.py` |
| Event backtest with annualised Sharpe | `apps/signals/backtest.py` |
| REST API | `POST /api/analyze`, `GET /api/health` |

## Success metrics

- **≥ 57%** post-earnings directional accuracy
- **≥ 80%** FLS extraction precision (cue + boilerplate-disqualifier design)
- **≥ 0.8** backtest Sharpe

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # add your HF_API_TOKEN for real model inference
# Django reads environment variables; it does not automatically load .env.
set -a
. ./.env
set +a

python manage.py migrate
python manage.py test         # offline — no token or network needed
python manage.py runserver    # Django API on :8000
```

Analyze a code-switched passage:

```bash
curl -s -X POST localhost:8000/api/analyze \
  -H 'Content-Type: application/json' \
  -d '{"text": "Revenue grew 15% year on year. Prestasi kumpulan dijangka kukuh, boleh tahan lah this quarter."}'
```

The response includes the document label/score, per-sentence model routing
(`finbert` vs `xlm-roberta`), and extracted forward-looking statements.

Scrape recent Bursa quarterly reports:

```bash
python manage.py scrape_bursa --pages 2 --analyze
```

If Bursa blocks automated access, download the quarterly-report PDF in your
browser from Bursa or the company's investor-relations site, then analyze it:

```bash
python manage.py analyze_pdf /path/to/report.pdf --offline > analysis.json
```

This extracts narrative text, routes English/BM sentences, scores sentiment,
and extracts forward-looking statements without network access or database
writes. The JSON includes extracted text and each sentence's `source`.
Omit `--offline` to use configured Hugging Face inference (which may fall back
to the lexicon). Scanned PDFs require OCR first. This manual path does not
restore automatic Bursa discovery or validate the live listing parser.

Run the gateway (optional, requires JDK 17 + Maven):

```bash
cd gateway && mvn spring-boot:run
```

See [integration setup and validation](docs/integration-validation.md) for
gateway prerequisites and live Hugging Face/Bursa checks.

## Four layers of agent design

1. **Surface — dual model routing.** Sentence-level detector (Manglish
   particles + BM lexicon) routes each sentence to the model that actually
   understands it.
2. **Structural — scrape → classify → ensemble.** A linear, inspectable
   pipeline: every stage persists artifacts (PDF, prose, per-sentence scores)
   so failures are attributable.
3. **Strategic — the MY NLP linguistic gap.** US-trained financial NLP treats
   BM tokens as noise; explicitly modelling code-switching recovers the signal.
4. **Root — the Bursa Manglish blind spot.** Bursa filings and calls mix
   registers in a way no off-the-shelf pipeline handles; the ensemble exists
   because no single model can.

## Testing

```bash
python manage.py test
```

Tests cover the language router, offline sentiment fallback, ensemble math,
FLS precision cases (incl. safe-harbor boilerplate rejection), the direction
model on synthetic data, the backtest (Sharpe/hit-rate), Bursa row parsing,
and the REST API — all fully offline.

### Optional local CPU inference

Hosted Hugging Face inference is the default. To run FinBERT and XLM-RoBERTa
on macOS, run these commands from the repository root using Python 3.11 or 3.12.
If you already created `.venv`, skip the first line.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-local.txt
```

The first request for each language downloads that model from Hugging Face.
Use a writable Hugging Face cache (set `HF_HOME` if needed).
Local predictions report `source: "local"`. After both models are cached,
set `HF_HUB_OFFLINE=1` to use only cached files. For the PDF command,
`--offline` explicitly selects the lexicon even when local inference is enabled.

To verify both models through the Django API without starting a server, run:

```bash
USE_LOCAL_INFERENCE=1 python manage.py shell <<'PYTHON'
from django.test import Client

response = Client().post(
    "/api/analyze",
    {"text": "Revenue grew and profits improved. Prestasi kumpulan kukuh dan keuntungan meningkat."},
    content_type="application/json",
)
print(response.json()["sentences"])
PYTHON
```

The MacBook Pro CPU run returned the following sentence predictions (scores rounded).

| Sentence | Model | Label | Score | Source |
|---|---|---|---:|---|
| Revenue grew and profits improved. | finbert | positive | 0.9590 | local |
| Prestasi kumpulan kukuh dan keuntungan meningkat. | xlm-roberta | positive | 0.7804 | local |

Check that both sentences report `source: "local"`. To serve the API with
the same backend, run `USE_LOCAL_INFERENCE=1 python manage.py runserver`.
