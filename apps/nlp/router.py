"""Layer 1 (surface): dual-model routing.

Splits a document into sentences and decides, per sentence, whether it is
formal English (route to FinBERT) or Manglish / Bahasa Malaysia
code-switched text (route to XLM-RoBERTa).
"""

import re
from dataclasses import dataclass

from .lexicon import BM_MARKERS, MANGLISH_PARTICLES

FINBERT = "finbert"
XLMR = "xlm-roberta"

# Fraction of tokens that must be BM/Manglish markers before a sentence is
# considered code-switched. A single particle ("lah") also forces XLM-R
# because particles are near-unambiguous.
BM_TOKEN_RATIO = 0.15

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")
_TOKEN = re.compile(r"[a-zA-Z']+")


@dataclass
class RoutedSentence:
    text: str
    model: str
    bm_ratio: float


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_SPLIT.split(text) if s.strip()]


def tokenize(sentence: str) -> list[str]:
    return [t.lower() for t in _TOKEN.findall(sentence)]


def bm_ratio(sentence: str) -> float:
    tokens = tokenize(sentence)
    if not tokens:
        return 0.0
    hits = sum(1 for t in tokens if t in BM_MARKERS)
    return hits / len(tokens)


def has_particle(sentence: str) -> bool:
    return any(t in MANGLISH_PARTICLES for t in tokenize(sentence))


def route_sentence(sentence: str) -> RoutedSentence:
    ratio = bm_ratio(sentence)
    if ratio >= BM_TOKEN_RATIO or has_particle(sentence):
        return RoutedSentence(sentence, XLMR, ratio)
    return RoutedSentence(sentence, FINBERT, ratio)


def route_document(text: str) -> list[RoutedSentence]:
    return [route_sentence(s) for s in split_sentences(text)]
