"""Hugging Face Inference API clients for the two sentiment models.

Both models return (label, score) with label in {positive, neutral, negative}.
When no HF_API_TOKEN is configured (local dev, CI) the clients fall back to a
deterministic lexicon scorer so the rest of the pipeline stays testable.
"""

import logging

import requests
from django.conf import settings

from .lexicon import NEGATIVE_WORDS, POSITIVE_WORDS
from .router import tokenize

logger = logging.getLogger(__name__)

API_URL = "https://api-inference.huggingface.co/models/{model}"
TIMEOUT = 30

# cardiffnlp/twitter-xlm-roberta-base-sentiment labels
_XLMR_LABEL_MAP = {"LABEL_0": "negative", "LABEL_1": "neutral", "LABEL_2": "positive"}


class SentimentResult(dict):
    """{'label': str, 'score': float, 'model': str, 'source': 'hf'|'lexicon'}"""


def _lexicon_score(text: str, model: str) -> SentimentResult:
    tokens = tokenize(text)
    pos = sum(1 for t in tokens if t in POSITIVE_WORDS)
    neg = sum(1 for t in tokens if t in NEGATIVE_WORDS)
    if pos > neg:
        label, score = "positive", min(1.0, 0.5 + 0.1 * (pos - neg))
    elif neg > pos:
        label, score = "negative", min(1.0, 0.5 + 0.1 * (neg - pos))
    else:
        label, score = "neutral", 0.5
    return SentimentResult(label=label, score=score, model=model, source="lexicon")


def _hf_request(model: str, text: str) -> SentimentResult | None:
    headers = {"Authorization": f"Bearer {settings.HF_API_TOKEN}"}
    try:
        resp = requests.post(
            API_URL.format(model=model),
            headers=headers,
            json={"inputs": text[:2000], "options": {"wait_for_model": True}},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        payload = resp.json()
    except (requests.RequestException, ValueError) as exc:
        logger.warning("HF inference failed for %s: %s", model, exc)
        return None
    # Response shape: [[{"label": ..., "score": ...}, ...]]
    try:
        scores = payload[0] if isinstance(payload[0], list) else payload
        best = max(scores, key=lambda d: d["score"])
        label = _XLMR_LABEL_MAP.get(best["label"], best["label"]).lower()
        return SentimentResult(
            label=label, score=float(best["score"]), model=model, source="hf"
        )
    except (KeyError, IndexError, TypeError) as exc:
        logger.warning("Unexpected HF payload for %s: %s", model, exc)
        return None


def score_sentence(text: str, model_name: str) -> SentimentResult:
    """Score one sentence with the given routed model.

    model_name is 'finbert' or 'xlm-roberta' (see router). Falls back to the
    lexicon scorer when the API is unavailable or unconfigured.
    """
    hf_model = settings.FINBERT_MODEL if model_name == "finbert" else settings.XLMR_MODEL
    if settings.HF_API_TOKEN:
        result = _hf_request(hf_model, text)
        if result is not None:
            return result
    return _lexicon_score(text, hf_model)
