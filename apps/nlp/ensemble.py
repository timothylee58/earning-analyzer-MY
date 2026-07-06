"""Layer 2 (structural): confidence-weighted ensemble vote.

Each routed sentence contributes a signed score (positive=+1, negative=-1,
neutral=0) weighted by model confidence. The document score is the weighted
mean in [-1, 1]; the label uses a dead zone around zero so mixed calls come
out neutral instead of flip-flopping.
"""

from dataclasses import dataclass, field

from .hf_client import SentimentResult, score_sentence
from .router import RoutedSentence, route_document

_SIGN = {"positive": 1.0, "neutral": 0.0, "negative": -1.0}
NEUTRAL_BAND = 0.1


@dataclass
class SentenceAnalysis:
    text: str
    model: str
    label: str
    score: float
    source: str


@dataclass
class DocumentAnalysis:
    label: str
    score: float
    n_sentences: int
    model_mix: dict = field(default_factory=dict)
    sentences: list = field(default_factory=list)


def aggregate(sentences: list[SentenceAnalysis]) -> DocumentAnalysis:
    if not sentences:
        return DocumentAnalysis(label="neutral", score=0.0, n_sentences=0)
    total_weight = sum(s.score for s in sentences)
    if total_weight == 0:
        doc_score = 0.0
    else:
        doc_score = sum(_SIGN[s.label] * s.score for s in sentences) / total_weight
    if doc_score > NEUTRAL_BAND:
        label = "positive"
    elif doc_score < -NEUTRAL_BAND:
        label = "negative"
    else:
        label = "neutral"
    mix: dict[str, int] = {}
    for s in sentences:
        mix[s.model] = mix.get(s.model, 0) + 1
    return DocumentAnalysis(
        label=label,
        score=round(doc_score, 4),
        n_sentences=len(sentences),
        model_mix=mix,
        sentences=sentences,
    )


def analyze_document(text: str) -> DocumentAnalysis:
    routed: list[RoutedSentence] = route_document(text)
    analyses = []
    for r in routed:
        result: SentimentResult = score_sentence(r.text, r.model)
        analyses.append(
            SentenceAnalysis(
                text=r.text,
                model=r.model,
                label=result["label"],
                score=result["score"],
                source=result["source"],
            )
        )
    return aggregate(analyses)
