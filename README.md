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

Run the gateway (optional, requires JDK 17 + Maven):

```bash
cd gateway && ./mvnw spring-boot:run   # or: mvn spring-boot:run
```

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
