---
name: tune-lexicon
description: Safely extend or tune the Manglish/BM routing lexicons and the offline sentiment lexicons in apps/nlp/lexicon.py — the most frequent change in this repo and the easiest to get subtly wrong. Use whenever adding BM/Manglish words, sentiment words, FLS cues, or adjusting BM_TOKEN_RATIO / NEUTRAL_BAND.
---

# Tune the lexicons without breaking routing

Routing IS the product: a wrong word in `BM_WORDS` silently sends English
sentences to the wrong model for every future analysis. Follow this
procedure for any change to `apps/nlp/lexicon.py`, `apps/nlp/router.py`
cues, or `apps/signals/fls.py` cue lists.

## Decide which list the word belongs in

| You are adding... | Goes in | Test to add |
|---|---|---|
| A Manglish particle (lah, lor, meh...) | `MANGLISH_PARTICLES` | Sentence with the particle routes to XLM-R even at low BM ratio |
| A BM function/finance word | `BM_WORDS` | BM sentence containing it routes to XLM-R |
| A sentiment word (EN or BM) | `POSITIVE_WORDS` / `NEGATIVE_WORDS` | `_lexicon_score` returns the right label |
| A forward-looking cue | `_EN_CUES` / `_BM_CUES` in `fls.py` | One positive + one near-miss negative test |

## The three hard rules

1. **The English-collision check (CLAUDE.md M6).** Before adding a word to
   `BM_WORDS` or `MANGLISH_PARTICLES`, ask: does this token appear in
   formal English earnings prose? Words like "margin", "asset"-cognates,
   "la" are the danger zone ("margin" is accepted because it's genuine BM
   finance vocabulary — that trade-off was made consciously; don't stack
   more like it without checking). Verify with:

   ```bash
   python3 -c "
   import django, os, sys; os.environ['DJANGO_SETTINGS_MODULE']='config.settings'; django.setup()
   from apps.nlp.router import route_document
   english = sys.stdin.read()
   for r in route_document(english):
       assert r.model == 'finbert', f'FLIPPED: {r.text[:60]} (ratio={r.bm_ratio:.2f})'
   print('OK: all English sentences still route to finbert')
   " <<'EOF'
   The Group recorded a profit before tax of RM12.4 million for the quarter.
   Revenue increased 15% year on year driven by loan growth and margin expansion.
   The Board declared an interim dividend of 2 sen per share.
   Operating expenses remained well controlled against the target set for the financial year.
   EOF
   ```

   Extend the heredoc with sentences containing your new word used in
   English context if such usage is plausible. Zero flips allowed.

2. **BM/EN pairing (CLAUDE.md rule 7).** Sentiment words and FLS cues are
   added in pairs: if you add "surge" to POSITIVE_WORDS, add its BM
   counterpart ("melonjak") in the same edit. If no natural counterpart
   exists, say so in the commit body.

3. **FLS cues are precision-first (CLAUDE.md M7).** Never add generic
   modals ("may", "could", "would", "mungkin") as cues. A cue must be a
   word that, on its own, makes an earnings sentence forward-looking ≥80%
   of the time.

## Threshold changes are escalations, not edits

`BM_TOKEN_RATIO` (router) and `NEUTRAL_BAND` (ensemble) shift behavior on
every document. Do not change them unilaterally — prepare before/after
routing and label counts on at least 3 realistic paragraphs (mixed, pure
EN, pure BM) and ask the user with the numbers (CLAUDE.md escalation rule 1).

## Finish

1. Add/extend the tests listed in the table above in `apps/nlp/tests.py`
   (or `apps/signals/tests.py` for FLS).
2. Run the `verify-pipeline` skill — Step 3's model_mix assertion is the
   final routing regression check.
3. Commit message body must list the exact words added, per list.
