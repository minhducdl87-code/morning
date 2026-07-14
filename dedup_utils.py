"""Dedup logic for Morning Digest: topic-agnostic field helper, title normalization,
fuzzy (Jaccard token-overlap) near-duplicate detection, recent titles/URLs extraction.
Split out of digest_utils.py to stay under the 200-LOC file guideline (paired with
url_check.py — digest_utils.py re-exports both as a thin facade)."""
import re
from datetime import datetime, timedelta

DEDUP_DAYS = 7  # rolling dedup window (was 3) — user rule: no repeat within 1 week


def list_item_fields(card: dict) -> list[str]:
    """Return keys pointing to a list of items — topic-agnostic (works for any config).
    Single source of truth — used by digest_utils, scrub_cards, generate_weekly,
    generate_monthly, notify-telegram (was duplicated in ≥5 places, see H4)."""
    return [k for k, v in card.items() if isinstance(v, list)]


# ── Title normalization for near-duplicate detection ─────────────────────────

_EMOJI_RE = re.compile(
    r'[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F2FF'
    r'\U0001F900-\U0001F9FF\U0001FA00-\U0001FAFF\U00002B00-\U00002BFF]+',
    flags=re.UNICODE,
)


def normalize_title(s: str) -> str:
    """Strip emoji, punctuation, lower, collapse whitespace. For fuzzy dedup match."""
    if not s:
        return ""
    s = _EMOJI_RE.sub("", s)
    s = re.sub(r"[^\w\s]", " ", s, flags=re.UNICODE)
    s = " ".join(s.lower().split())
    return s


# Stopwords VN + EN, không dùng để tính similarity (không phải content-bearing)
_STOPWORDS = frozenset({
    "và","của","với","để","cho","là","có","bị","được","đã","sẽ","đang","một","các","những",
    "này","đó","kia","về","từ","trong","ngoài","trên","dưới","hoặc","hay","khi","nếu","thì",
    "vì","bởi","do","giờ","đến","tại","theo","cả","chỉ","mới","sau","trước","cùng","như",
    "và","hơn","rất","ra","vào","đi","lại","tới","xuống","lên","qua",
    "the","a","an","of","to","for","with","in","on","at","and","or","but","is","are","was",
    "were","be","been","being","has","have","had","do","does","did","will","would","should",
    "could","may","might","can","just","from","by","this","that","these","those","new",
})

def _tokens(s: str) -> set:
    """Content-bearing word set from normalized title. Drops stopwords + 1-char tokens."""
    return {w for w in normalize_title(s).split() if len(w) > 1 and w not in _STOPWORDS}


def build_dedup_index(titles: list) -> tuple[set, list]:
    """Build (exact_norms, token_sets_list) for dedup lookup."""
    exact = {normalize_title(t) for t in titles if t}
    exact.discard("")
    tokens_list = [_tokens(t) for t in titles if t]
    tokens_list = [ts for ts in tokens_list if len(ts) >= 2]
    return exact, tokens_list


def is_duplicate_title(title: str, exact_norms: set, tokens_list: list, threshold: float = 0.55) -> bool:
    """Duplicate if:
      1. Exact normalized match, OR
      2. Jaccard(new_tokens, any_recent_tokens) >= threshold
    Threshold 0.55 = 55% content-word overlap catches paraphrases + reorderings."""
    if not title:
        return False
    nt = normalize_title(title)
    if not nt:
        return False
    if nt in exact_norms:
        return True
    new_tok = _tokens(title)
    if len(new_tok) < 2:
        return False
    for recent_tok in tokens_list:
        union = new_tok | recent_tok
        if not union:
            continue
        jaccard = len(new_tok & recent_tok) / len(union)
        if jaccard >= threshold:
            return True
    return False


def get_recent_titles(cards: list, date_str: str, now, days: int = DEDUP_DAYS) -> list:
    """Extract titles from all list-fields in cards of last N days (topic-agnostic)."""
    cutoff = (now - timedelta(days=days)).date()
    titles = []
    for c in cards:
        if c.get("date") == date_str:
            continue
        try:
            card_date = datetime.strptime(c["date"], "%Y-%m-%d").date()
        except (ValueError, KeyError):
            continue
        if card_date >= cutoff:
            for f in list_item_fields(c):
                titles += [x["title"] for x in c.get(f, []) if isinstance(x, dict) and x.get("title")]
    return titles


def get_recent_urls(cards: list, date_str: str, now, days: int = DEDUP_DAYS) -> set:
    """Extract URLs from all list-fields in cards of last N days (topic-agnostic)."""
    cutoff = (now - timedelta(days=days)).date()
    urls = set()
    for c in cards:
        if c.get("date") == date_str:
            continue
        try:
            card_date = datetime.strptime(c["date"], "%Y-%m-%d").date()
        except (ValueError, KeyError):
            continue
        if card_date >= cutoff:
            for f in list_item_fields(c):
                urls |= {x["url"] for x in c.get(f, []) if isinstance(x, dict) and x.get("url")}
    return urls - {""}
