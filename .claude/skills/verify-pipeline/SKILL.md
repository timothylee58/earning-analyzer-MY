---
name: verify-pipeline
description: Full offline verification of the earnings-analyzer pipeline — test suite plus a live-server smoke test with a mixed EN/BM/Manglish fixture. Run after ANY change to apps/, config/, or requirements.txt, and before every commit. Catches silent routing shifts, lexicon regressions, and API contract breaks.
---

# Verify the pipeline

Run this after any code change and before claiming "done". It is the
project's definition of verified. Total runtime ~15 seconds.

## Step 1 — Test suite (the gate)

```bash
python3 manage.py test
```

Expected: `OK`, 31+ tests, zero skips. If any test fails:
- A sentiment-label failure means the lexicon is missing a word — fix
  `apps/nlp/lexicon.py`, never the test (CLAUDE.md M1).
- A shape error from `direction.py` means the `N_FEATURES` contract broke —
  grep `N_FEATURES` and `(n, 4)` across `apps/signals/` (CLAUDE.md M4).

## Step 2 — Live-server smoke test

Start the server and hit `/api/analyze` with the canonical mixed-register
fixture. This catches wiring problems the unit tests can't (urls, csrf,
JSON boundary):

```bash
python3 manage.py migrate --run-syncdb -v0
python3 manage.py runserver 8000 >/dev/null 2>&1 &
sleep 3
curl -s -X POST localhost:8000/api/analyze \
  -H 'Content-Type: application/json' \
  -d '{"text": "Revenue grew 15% year on year. Prestasi kumpulan dijangka kukuh, boleh tahan lah this quarter. The Group expects margins to improve in FY2027."}' \
  | python3 -m json.tool
pkill -f runserver
```

## Step 3 — Assert these facts on the response (all must hold)

1. `sentiment.label` == `"positive"` and `sentiment.n_sentences` == `3`.
2. `sentiment.model_mix` == `{"finbert": 2, "xlm-roberta": 1}` — the BM
   sentence and ONLY the BM sentence routed to XLM-R. If this drifted, a
   lexicon or router change silently moved routing: stop and diagnose
   before committing (CLAUDE.md M6).
3. Every sentence has `source` == `"lexicon"` (no `HF_API_TOKEN` in this
   environment). If any sentence says `"hf"`, a token is leaking into the
   test environment — investigate.
4. `forward_looking_statements` contains exactly the FY2027 sentence
   (the "expects ... FY2027" one). The historical revenue sentence must
   NOT appear (FLS precision contract, CLAUDE.md M7).
5. `GET /api/health` returns `{"status": "ok"}`.

## Step 4 — Repo hygiene before commit

```bash
git status --short
```

- `db.sqlite3`, `data/`, `.env` must not be staged (gitignored, but check).
- If any file in `apps/scraper/models.py` changed, a migration must be in
  the diff.

## Reporting

State in your summary: test count + OK, and that the smoke-test assertions
in Step 3 held (call out routing counts explicitly). If you changed
`gateway/`, add: "gateway not compiled here (no JDK)".
