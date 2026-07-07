# CLAUDE.md — Operating Manual

Earnings Analyzer Malaysia: Bursa quarterly PDF scraper + dual NLP pipeline.
FinBERT scores formal English; XLM-RoBERTa scores Manglish/Bahasa Malaysia
code-switched text. Read `README.md` for architecture; read this file for how
to work here without breaking things.

## The one design rule that explains everything else

**Every path must work offline.** The HF Inference API, the Bursa website,
and price data are all external and all optional. Each has a deterministic
offline substitute (lexicon scorer, recorded fixtures, synthetic data), and
the offline path is the path that tests exercise. If you add a capability
that only works with a network or a token, you have broken the design —
add the offline fallback first, then the real integration.

## Map

| Path | What it is | External dependency |
|---|---|---|
| `config/` | Django settings/urls/wsgi. Env-driven config lives in `settings.py` only. | — |
| `apps/scraper/` | Bursa announcement list → PDF → prose text. ORM models live here. | bursamalaysia.com |
| `apps/nlp/` | Language router, HF clients, ensemble, `/api/analyze`. | HF Inference API |
| `apps/signals/` | FLS extraction, direction model, backtest. | — (pure numpy) |
| `gateway/` | Spring Boot proxy (Java 17). Not built or tested in this sandbox — no JDK/Maven here. | — |

Pipeline order: `bursa.py → pdf_extract.py → router.py → hf_client.py →
ensemble.py → fls.py → direction.py → backtest.py`. Data flows one way;
never import backwards (e.g. `nlp` must not import from `signals` — note
`views.py` imports `signals.fls`, which is forward: views are the top).

## Conventions I follow (keep these)

1. **Apps live under `apps/` with short labels** (`label = "nlp"` in
   `apps.py`). New Django apps follow the same pattern: `apps/<name>/`,
   explicit `AppConfig`, registered in `INSTALLED_APPS` as `apps.<name>`.
2. **Django test framework, not pytest.** Tests are `tests.py` per app,
   `django.test.TestCase`, run via `python manage.py test`. Don't introduce
   pytest, fixtures files, or conftest.
3. **Heavy imports are lazy.** `pdfplumber` is imported inside the function
   that uses it (`pdf_extract.extract_text`). `transformers`/`torch` are
   commented out in requirements — model inference happens over HTTP, not
   in-process. Keep it that way; this repo must `manage.py test` on a bare
   `pip install Django requests numpy`.
4. **`apps/signals/` is pure numpy.** No sklearn, no pandas, no torch. The
   logistic regression in `direction.py` is deliberately hand-rolled — it is
   a portfolio artifact and a dependency-weight decision, not an oversight.
5. **Dataclasses for pipeline records** (`RoutedSentence`,
   `SentenceAnalysis`, `DocumentAnalysis`, `BacktestResult`), dicts only at
   the JSON boundary (views, `SentimentResult`).
6. **Config through `django.conf.settings`, values from env** with safe
   defaults (`HF_API_TOKEN`, `FINBERT_MODEL`, `XLMR_MODEL`). Never read
   `os.environ` outside `settings.py`.
7. **Bilingual by default.** Any lexicon, cue list, or regex that handles
   English gets a Bahasa Malaysia counterpart in the same change
   (see `lexicon.py`, `fls.py` — EN and BM lists are always paired).
8. **Scraper etiquette:** identifying User-Agent, `RATE_LIMIT_SECONDS`
   sleep between downloads, small pages, cache-to-disk before re-fetching.
9. **Git:** imperative commit subject + a body that lists what changed per
   app. Work happens on `claude/...` branches; PRs open as drafts; `main`
   is merge-only. Never commit `db.sqlite3`, `.env`, or `data/`.

## Conventions to adopt (I'd add these — they're now the rule)

10. **Every threshold is a named module constant** with a comment saying
    what moves it (`BM_TOKEN_RATIO`, `NEUTRAL_BAND`, `_MIN_WORDS`). No
    inline magic numbers in new code.
11. **New API endpoints:** view in the owning app's `views.py`, route in
    that app's `urls.py`, included from `config/urls.py` under `/api/`.
    POST views need `@csrf_exempt` (there is no session auth; the gateway
    owns auth). Every endpoint gets a request-validation test and a
    happy-path test.
12. **Label vocabulary is closed:** sentiment labels are exactly
    `positive | neutral | negative`, lowercase, everywhere past
    `hf_client.py`. Any new model's raw labels get mapped there (see
    `_XLMR_LABEL_MAP`) — never leak `LABEL_0` downstream.
13. **Migrations ship with model changes** in the same commit
    (`python manage.py makemigrations scraper`).

## Named mistakes a weaker model will make here, and the rule that prevents each

**M1. "The sentiment test fails, so I'll relax the test."**
The offline lexicon scorer is intentionally small; a test asserting
`positive` on a reasonable sentence that comes back `neutral` means the
lexicon is missing a word. *Rule: fix `lexicon.py` (add the word to
POSITIVE/NEGATIVE_WORDS), never weaken the assertion. This exact failure
already happened once ("grew"/"improve" were missing).*

**M2. "I'll add sklearn for the model / pandas for the backtest."**
*Rule: `apps/signals/` stays numpy-only. If an algorithm genuinely needs
more, stop and ask — it's a scope decision, not a convenience decision.*

**M3. Writing a test that calls the HF API or bursamalaysia.com.**
It will pass locally-with-token and fail everywhere else. *Rule: tests never
touch the network. Test the fallback path, parse recorded fixtures for the
scraper (see `ParseRowTests` — it feeds `parse_row` literal HTML rows), and
if you must test `_hf_request`, mock `requests.post`.*

**M4. Adding a direction-model feature and updating only one file.**
`N_FEATURES = 4` in `direction.py` is a contract enforced by a shape check
that will raise at train time. *Rule: changing the feature vector touches,
in order: the docstring feature list and `N_FEATURES` in `direction.py`,
every synthetic-data helper in `apps/signals/tests.py` (`size=(n, 4)`
appears in several tests), and the feature assembly wherever announcements
are converted to vectors. Grep for `N_FEATURES` and `(n, 4)` before you
claim done.*

**M5. Treating `apps/signals` as Django signals.**
The name collides with `django.dispatch` conventions. *Rule: this app is
trading signals. Django signal receivers (post_save etc.) do not belong
here — if you ever need them, they go in the app that owns the model, in
a file named `receivers.py`, wired in `AppConfig.ready()`.*

**M6. Making the router "smarter" and silently changing routing.**
Routing is the product. A lexicon addition that overlaps common English
(e.g. adding "bank", "margin" already flirts with this — "margin" IS in
BM_WORDS because it's valid BM) shifts sentences to XLM-R. *Rule: after any
change to `lexicon.py` or `router.py`, run the router tests AND spot-check
`route_document` on one pure-English Bursa paragraph — zero sentences may
flip to xlm-roberta. Never add a word to `BM_WORDS` that is more common in
English than in BM without checking this.*

**M7. Breaking the FLS precision contract to gain recall.**
The success metric is precision ≥ 80%; recall is sacrificial. *Rule: new
cues in `fls.py` must be specific ("expects", "menjangka"), never generic
("may", "could", "future"). Every new cue ships with one positive test and
one near-miss negative test (like the safe-harbor case).*

**M8. Forgetting the annualisation or ddof in backtest math.**
*Rule: Sharpe = mean/std(ddof=1) × √(252/holding_days). Any change to
`backtest.py` must keep `test_perfect_signal_has_positive_sharpe` and the
empty/mismatch edge cases passing unmodified.*

**M9. Hammering Bursa while debugging the scraper.**
*Rule: fetch a page once, save the JSON/HTML to a local file, and iterate
against the file. Never loop live requests; never remove
`RATE_LIMIT_SECONDS` or the identifying User-Agent.*

**M10. Editing `gateway/` and claiming it works.**
There is no JDK or Maven in this sandbox; Java changes cannot be compiled
here. *Rule: keep gateway edits minimal and mechanical, say explicitly in
the PR that the gateway is untested, and never let a Python task grow a
Java surface.*

**M11. Hardcoding secrets or new env reads.**
*Rule: new config = `settings.py` entry with default + `.env.example`
entry, in the same commit. `HF_API_TOKEN` must never appear in code, tests,
fixtures, or PR text.*

## Quality bar per deliverable (checkable, in order)

**Any code change:**
- [ ] `python manage.py test` passes with no token, no network, on
      `Django + requests + numpy` only.
- [ ] No new dependency in `requirements.txt` unless the task explicitly
      called for one.
- [ ] New/changed thresholds are named constants (rule 10).

**New/changed API endpoint:**
- [ ] Route lives in the owning app's `urls.py`; view returns `JsonResponse`.
- [ ] Rejects bad input with 400 + `{"error": ...}` (test exists).
- [ ] Happy-path test asserts response shape, not just status 200.
- [ ] Smoke-tested against a live `runserver` with curl at least once.

**Lexicon/router change:**
- [ ] Router tests pass; pure-English paragraph still routes 100% finbert (M6).
- [ ] BM/EN pairing maintained (rule 7).

**Scraper change:**
- [ ] Parsing logic is testable from a recorded row/page fixture with no
      network (M3, M9).
- [ ] `parse_row` stays defensive: missing links/ids degrade to skip, not crash.

**Model/backtest change:**
- [ ] Deterministic: every RNG takes an explicit seed.
- [ ] Synthetic-data test proves the model learns (accuracy bound), not
      just runs.
- [ ] Shape/length validation raises `ValueError` with a message (existing
      pattern in `direction.py`, `backtest.py`).

**PR:**
- [ ] Draft first. Title = what, body = per-app summary + test evidence
      (count + how verified).
- [ ] Migrations included iff models changed. No `db.sqlite3`, `.env`,
      `data/` in the diff.
- [ ] If `gateway/` was touched: body states it is uncompiled/untested here.

## When uncertain: escalation rules

Ask the user (AskUserQuestion / PR comment) — do not guess — when:
1. **A metric trade-off is involved.** Anything that could move the three
   success metrics (57% directional accuracy, 80% FLS precision, 0.8
   Sharpe) in opposite directions — e.g. recall-vs-precision cue changes,
   `BM_TOKEN_RATIO` or `NEUTRAL_BAND` retuning. Present the trade-off with
   before/after numbers on a concrete sample.
2. **A dependency or service would be added** (sklearn, pandas, celery, a
   new external API, a paid tier). Name the alternative you'd use inside
   current constraints.
3. **Scraping behavior would intensify** — more pages, shorter sleeps,
   new endpoints on bursamalaysia.com. Default answer is no.
4. **A reviewer comment has two readings** that lead to different diffs.
   Quote the comment, state both readings, ask which.
5. **The HF API response shape doesn't match `_hf_request`'s parser.**
   Don't silently ride the lexicon fallback in production paths — that
   masks a real outage. Fix the parser if the new shape is documented;
   otherwise report it.

Decide yourself (do NOT ask) when:
- Adding clearly-sentiment-bearing words to the offline lexicon (M1).
- Adding tests, docstrings, defensive parsing, named constants.
- Fixing anything where an existing test or this file already states the
  rule — the rule is the answer.
- Choosing between two implementations that are behavior-identical at the
  API boundary: pick the one matching existing patterns and note it in the PR.

If truly blocked (external service dead, ambiguous and user unreachable):
implement behind the offline path, mark the live path with a `# TODO(<topic>)`
comment, state the block explicitly in the PR body — never claim it works.

## Commands

```bash
python manage.py test                      # full offline suite (the gate)
python manage.py test apps.nlp             # one app
python manage.py runserver                 # API on :8000
python manage.py migrate                   # sqlite dev db
python manage.py scrape_bursa --pages 1 --analyze   # live scrape (network!)
```
