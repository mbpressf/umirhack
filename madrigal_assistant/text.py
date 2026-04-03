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

EMOJI_PATTERN = re.compile(r"[\U00010000-\U0010ffff]|\ufe0f")
URL_PATTERN = re.compile(r"https?://\S+", flags=re.IGNORECASE)
NOISE_PATTERNS = [
    re.compile(r"(?:❌\s*){2,}.*$", flags=re.IGNORECASE),
    re.compile(r"с обходами блокировок телеграм[^.?!]*(?:[.?!]|$)", flags=re.IGNORECASE),
    re.compile(r"дальше блокировки только усилятся[^.?!]*(?:[.?!]|$)", flags=re.IGNORECASE),
    re.compile(r"подпишитесь на (?:резерв|наш резерв)[^.?!]*(?:[.?!]|$)", flags=re.IGNORECASE),
    re.compile(r"подпишись на [^.!?]*(?:max|вк|@\w+)[^.?!]*(?:[.?!]|$)", flags=re.IGNORECASE),
    re.compile(r"подписывайся на [^.!?]*(?:max|вк|@\w+)[^.?!]*(?:[.?!]|$)", flags=re.IGNORECASE),
    re.compile(r"что делать, когда интернет не работает\??\s*читать нас здесь\.?", flags=re.IGNORECASE),
    re.compile(r"читать нас здесь\.?", flags=re.IGNORECASE),
    re.compile(r"читай max\b[^.?!]*(?:[.?!]|$)", flags=re.IGNORECASE),
    re.compile(r"мы в max\b[^.?!]*(?:[.?!]|$)", flags=re.IGNORECASE),
    re.compile(r"подробнее здесь[^.?!]*(?:[.?!]|$)", flags=re.IGNORECASE),
    re.compile(r"объявления\s+работа\s+купи/продай[^.?!]*(?:[.?!]|$)", flags=re.IGNORECASE),
    re.compile(r"видео:\s*соцсети[^.?!]*(?:[.?!]|$)", flags=re.IGNORECASE),
    re.compile(r"подпишитесь[^.?!]*(?:max\.ru|в\s+max)[^.?!]*(?:[.?!]|$)", flags=re.IGNORECASE),
    re.compile(r"(?:наш|на)\s+резерв\s+в\s+max\b[^.?!]*(?:[.?!]|$)", flags=re.IGNORECASE),
]
PROMO_MARKERS = {
    "скидк",
    "акция",
    "заказать",
    "купить",
    "цена",
    "цены",
    "доставка",
    "звоните",
    "ассортимент",
    "товаров",
    "благоустраивайте",
    "приобретая",
    "дизайнерские проекты",
    "подробности",
    "узнать",
    "продукц",
    "тротуарн",
    "продан",
    "продают",
    "перекуп",
    "рыночн",
    "чат",
}
ISSUE_HINTS = {
    "жалоб",
    "авар",
    "пожар",
    "дтп",
    "очеред",
    "запах",
    "отключ",
    "поликлин",
    "больниц",
    "сбили",
    "погиб",
    "гари",
    "дым",
    "мошенн",
}


def strip_html(raw_text: str | None) -> str:
    if not raw_text:
        return ""
    text = re.sub(r"<br\s*/?>", " ", raw_text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    return " ".join(text.split())


def clean_public_text(raw_text: str | None) -> str:
    if not raw_text:
        return ""
    text = strip_html(raw_text)
    text = EMOJI_PATTERN.sub("", text)
    text = URL_PATTERN.sub(" ", text)
    text = re.sub(r"\bmax\.ru/\S+\b", " ", text, flags=re.IGNORECASE)
    for pattern in NOISE_PATTERNS:
        text = pattern.sub(" ", text)
    text = re.sub(r"(?:\s*[|•·]+\s*)+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" \t\r\n-—|,.;:!?")


def normalize_text(raw_text: str | None) -> str:
    text = clean_public_text(raw_text).lower()
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


def looks_like_promotional_noise(text: str | None, title: str | None = None) -> bool:
    normalized = normalize_text(" ".join(part for part in [title or "", text or ""] if part))
    if not normalized:
        return False
    promo_hits = sum(1 for marker in PROMO_MARKERS if marker in normalized)
    issue_hits = sum(1 for marker in ISSUE_HINTS if marker in normalized)
    strong_cta = any(
        marker in normalized
        for marker in {"заказать", "купить", "доставка", "ассортимент", "скидк", "прода", "цена", "чат"}
    )
    return promo_hits >= 4 and issue_hits == 0 and strong_cta


def top_keywords(texts: list[str], limit: int = 5) -> list[str]:
    counter: Counter[str] = Counter()
    for text in texts:
        counter.update(tokenize(text))
    return [token for token, _ in counter.most_common(limit)]
