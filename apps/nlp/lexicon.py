"""Lexicons for Manglish / Bahasa Malaysia detection and offline sentiment.

Standard FinBERT is trained on formal US-market English, so Malay function
words and Manglish discourse particles are out-of-vocabulary noise to it.
These lexicons let the router send code-switched sentences to XLM-RoBERTa
instead, and provide a deterministic offline fallback scorer for tests and
development without a Hugging Face API token.
"""

# Manglish discourse particles — near-unambiguous code-switch markers.
MANGLISH_PARTICLES = {
    "lah", "la", "lor", "leh", "meh", "mah", "hor", "wor", "liao", "kan",
    "kah", "ler", "gua", "wan", "sia",
}

# High-frequency Bahasa Malaysia function/content words seen in Bursa
# quarterly reports, MD&A sections and analyst-call transcripts.
BM_WORDS = {
    # function words
    "yang", "dan", "atau", "untuk", "dengan", "kepada", "daripada", "dalam",
    "pada", "ini", "itu", "juga", "tidak", "tak", "akan", "sudah", "belum",
    "boleh", "kena", "ada", "tiada", "sahaja", "saja", "lebih", "kurang",
    "sangat", "amat", "kami", "kita", "mereka", "adalah", "ialah", "telah",
    "sedang", "masih", "seperti", "kerana", "tetapi", "namun", "serta",
    # finance / earnings vocabulary
    "keuntungan", "kerugian", "pendapatan", "hasil", "perbelanjaan", "kos",
    "suku", "tahunan", "dividen", "saham", "pelabur", "pelaburan", "pasaran",
    "syarikat", "kumpulan", "prestasi", "pertumbuhan", "penurunan",
    "peningkatan", "jangkaan", "unjuran", "margin", "aliran", "tunai",
    "hutang", "aset", "liabiliti", "ekuiti", "ringgit", "juta", "bilion",
    "menjangka", "dijangka", "meningkat", "menurun", "berkurangan",
    "bertambah", "kukuh", "lemah", "cabaran", "peluang", "prospek",
}

BM_MARKERS = MANGLISH_PARTICLES | BM_WORDS

# Offline fallback sentiment lexicon (English + BM), used only when no
# HF_API_TOKEN is configured. Deliberately small and high-precision.
POSITIVE_WORDS = {
    "growth", "grew", "profit", "gain", "gains", "improve", "improved",
    "improvement", "strong", "strongly",
    "stronger", "record", "exceed", "exceeded", "beat", "resilient", "robust",
    "higher", "increase", "increased", "expansion", "upgrade", "optimistic",
    "keuntungan", "peningkatan", "meningkat", "kukuh", "bertambah", "peluang",
    "cemerlang", "untung",
}

NEGATIVE_WORDS = {
    "loss", "losses", "decline", "declined", "weak", "weaker", "impairment",
    "downgrade", "miss", "missed", "lower", "decrease", "decreased", "drop",
    "shortfall", "headwind", "headwinds", "challenging", "deteriorate",
    "kerugian", "penurunan", "menurun", "lemah", "berkurangan", "cabaran",
    "rugi", "susut",
}
