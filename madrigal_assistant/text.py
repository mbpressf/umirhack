from __future__ import annotations

import hashlib
import re
from collections import Counter
from html import unescape

STOPWORDS = {
    "а",
    "без",
    "более",
    "был",
    "были",
    "в",
    "во",
    "все",
    "для",
    "до",
    "его",
    "ее",
    "же",
    "за",
    "из",
    "или",
    "и",
    "к",
    "как",
    "когда",
    "на",
    "не",
    "но",
    "о",
    "об",
    "от",
    "по",
    "под",
    "после",
    "при",
    "про",
    "с",
    "со",
    "также",
    "то",
    "у",
    "что",
    "это"
}


def strip_html(raw_text: str | None) -> str:
    if not raw_text:
        return ""
    text = re.sub(r"<br\s*/?>", " ", raw_text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    return " ".join(text.split())


def normalize_text(raw_text: str | None) -> str:
    text = strip_html(raw_text).lower()
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"[^0-9a-zа-яё\s-]", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def tokenize(raw_text: str | None) -> list[str]:
    text = normalize_text(raw_text)
    return [token for token in text.split() if len(token) > 2 and token not in STOPWORDS]


def shorten(text: str | None, limit: int = 180) -> str:
    if not text:
        return ""
    collapsed = " ".join(text.split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: limit - 1].rstrip() + "…"


def first_sentence(text: str | None) -> str:
    if not text:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", " ".join(text.split()))
    return parts[0].strip()


def stable_event_id(*parts: str) -> str:
    digest = hashlib.sha1("||".join(parts).encode("utf-8")).hexdigest()
    return digest[:16]


def top_keywords(texts: list[str], limit: int = 5) -> list[str]:
    counter: Counter[str] = Counter()
    for text in texts:
        counter.update(tokenize(text))
    return [token for token, _ in counter.most_common(limit)]
