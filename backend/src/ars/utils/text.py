
from __future__ import annotations

import hashlib
import re
import unicodedata

_WORD = re.compile(r"[^\W_]+", re.UNICODE)
_SENTENCE = re.compile(r"(?<=[.!?¿¡])\s+")


def fold(text: str) -> str:

    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


STOPWORDS_ES = {
    fold(w)
    for w in """a al algo ante con contra cual cuando de del desde donde e el ella ellos en entre era es esa ese eso esta este
esto fue ha han hay la las le les lo los me mi muy ni no nos o para pero por porque que quien se si sin sobre son su sus tambien tan te tiene
un una uno unas unos y ya como cada cuales segun sido ser estan""".split()
}
STOPWORDS_EN = {
    fold(w)
    for w in """a about after all also an and any are as at be because been but by can could did do does for from had has
have how if in into is it its may more most no not of on or other our out over should so some such than that the their them then there these
they this to was were what when where which while who why will with would you your""".split()
}
STOPWORDS = STOPWORDS_ES | STOPWORDS_EN


def tokenize(text: str) -> list[str]:
    return _WORD.findall(fold(text))


def content_tokens(text: str, min_len: int = 3) -> list[str]:

    return [
        t
        for t in tokenize(text)
        if (len(t) >= min_len or t.isdigit()) and t not in STOPWORDS
    ]


def fts_terms(query: str, limit: int = 24) -> list[str]:

    seen: dict[str, None] = {}
    for tok in _WORD.findall(query.lower()):
        if len(tok) > 1 and fold(tok) not in STOPWORDS:
            seen.setdefault(tok, None)
    return list(seen)[:limit]


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE.split(text) if s.strip()]


def approx_tokens(text: str) -> int:

    return max(1, len(text) // 4) if text else 0


def truncate_chars(text: str, limit: int) -> str:
    return (
        text if len(text) <= limit else text[: max(0, limit - 1)].rstrip() + "…"
    )


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def sha256_hex(data: bytes | str) -> str:
    return hashlib.sha256(
        data.encode("utf-8") if isinstance(data, str) else data
    ).hexdigest()


def detect_language(text: str) -> str:
   
    toks = set(tokenize(text))
    es, en = len(toks & STOPWORDS_ES), len(toks & STOPWORDS_EN)
    if es == en == 0:
        return "other"
    return "es" if es >= en else "en"
