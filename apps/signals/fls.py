"""Forward-looking statement (FLS) extraction.

Precision-first (target >= 80%): a sentence is FLS only when it contains a
forward-looking cue (EN or BM) AND is not disqualified by a hedge that marks
it as boilerplate/safe-harbor language.
"""

import re

from apps.nlp.router import split_sentences

# English forward-looking cues, aligned with SEC/Bursa MD&A phrasing.
_EN_CUES = [
    r"\bexpects?\b", r"\bexpected\b", r"\banticipates?\b", r"\bforecasts?\b",
    r"\bprojects?\b", r"\bguidance\b", r"\boutlook\b", r"\bwill\s+(?:be|continue|remain|grow|improve|increase|decrease|focus)\b",
    r"\bplans?\s+to\b", r"\baims?\s+to\b", r"\btargets?\b", r"\bgoing\s+forward\b",
    r"\bnext\s+(?:quarter|year|financial\s+year)\b", r"\bFY\s?20\d{2}\b",
    r"\bremains?\s+(?:optimistic|cautious|confident)\b",
]

# Bahasa Malaysia forward-looking cues.
_BM_CUES = [
    r"\bmenjangka\b", r"\bdijangka\b", r"\bjangkaan\b", r"\bunjuran\b",
    r"\bakan\s+(?:terus|meningkat|menurun|kekal|memberi)\b",
    r"\bmerancang\b", r"\bmensasarkan\b", r"\bsasaran\b", r"\bprospek\b",
    r"\bpada\s+masa\s+hadapan\b", r"\btahun\s+kewangan\s+akan\s+datang\b",
]

# Disqualifiers: safe-harbor boilerplate, not actual guidance.
_BOILERPLATE = [
    r"safe\s+harbou?r", r"forward[- ]looking\s+statements?\s+(?:are|involve|within)",
    r"undue\s+reliance", r"private\s+securities\s+litigation",
]

_CUE_RE = re.compile("|".join(_EN_CUES + _BM_CUES), re.IGNORECASE)
_BOILERPLATE_RE = re.compile("|".join(_BOILERPLATE), re.IGNORECASE)


def is_fls(sentence: str) -> bool:
    if _BOILERPLATE_RE.search(sentence):
        return False
    return bool(_CUE_RE.search(sentence))


def extract_fls(text: str) -> list[str]:
    return [s for s in split_sentences(text) if is_fls(s)]
