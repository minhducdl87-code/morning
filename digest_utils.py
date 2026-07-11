"""Shared utilities for Morning Digest generators."""
import re
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

DEDUP_DAYS = 7  # rolling dedup window (was 3) — user rule: no repeat within 1 week

GITHUB_REPO_RE = re.compile(r"^https://github\.com/[^/\s]+/[^/\s]+/?$")
HTTP_TIMEOUT   = 5
HEAD_WORKERS   = 8

# Domains we consider "not a real source" — short-lived redirects, schema leaks
URL_BLACKLIST  = (
    "vertexaisearch.cloud.google.com",  # Gemini grounding redirect with expiring token
    "link-ho",                           # schema literal leak ("link-hoặc-...")
)


def _list_fields(card: dict) -> list[str]:
    """Return keys pointing to a list of items — topic-agnostic (works for any config)."""
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


def title_prefix(s: str, n_words: int = 5) -> str:
    """First N normalized words — catches paraphrase reordering."""
    words = normalize_title(s).split()
    return " ".join(words[:n_words])


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
    Threshold 0.6 = 60% content-word overlap catches paraphrases + reorderings."""
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
            for f in _list_fields(c):
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
            for f in _list_fields(c):
                urls |= {x["url"] for x in c.get(f, []) if isinstance(x, dict) and x.get("url")}
    return urls - {""}


# ── URL liveness check (HEAD with redirect follow) ─────────────────────────────

def is_url_live(url: str) -> bool:
    """Return True if URL responds 2xx/3xx within timeout. Used to drop 404 fake links."""
    if not url or not url.startswith("http"):
        return False
    if " " in url:
        return False
    if any(bad in url for bad in URL_BLACKLIST):
        return False
    try:
        req = urllib.request.Request(url, method="HEAD")
        req.add_header("User-Agent", "Mozilla/5.0 morning-digest")
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            return 200 <= resp.status < 400
    except urllib.error.HTTPError as e:
        # Some servers return 405 for HEAD but URL is fine — try GET range
        if e.code in (403, 405, 429):
            try:
                req = urllib.request.Request(url, method="GET")
                req.add_header("User-Agent", "Mozilla/5.0 morning-digest")
                req.add_header("Range", "bytes=0-0")
                with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
                    return 200 <= resp.status < 400
            except Exception:
                return False
        return False
    except Exception:
        return False


def batch_check_urls(urls: list[str]) -> dict[str, bool]:
    """Parallel HEAD check. Returns {url: is_live}."""
    urls = list({u for u in urls if u})
    if not urls:
        return {}
    result = {}
    with ThreadPoolExecutor(max_workers=HEAD_WORKERS) as pool:
        futures = {pool.submit(is_url_live, u): u for u in urls}
        for fut in as_completed(futures):
            url = futures[fut]
            try:
                result[url] = fut.result()
            except Exception:
                result[url] = False
    return result


# ── Validation: clear bad news URLs, drop bad repo items ──────────────────────

def validate_news_items(items: list, live_map: dict) -> list:
    """STRICT: drop news items without live URL. Top rule — news must have real source."""
    cleaned = []
    for n in items:
        url = (n.get("url") or "").strip()
        if not url:
            print(f"  [validate] dropped news (no URL): {n.get('title','')[:60]}")
            continue
        if not live_map.get(url, False):
            print(f"  [validate] dropped news (dead URL): {url}")
            continue
        cleaned.append(n)
    return cleaned


def validate_repo_items(items: list, live_map: dict) -> list:
    """Drop repo items whose URL is not github.com/owner/repo OR is dead."""
    cleaned = []
    for r in items:
        url = (r.get("url") or "").strip()
        if not GITHUB_REPO_RE.match(url):
            print(f"  [validate] dropped repo (bad format): {url}")
            continue
        if not live_map.get(url, False):
            print(f"  [validate] dropped repo (dead URL): {url}")
            continue
        cleaned.append(r)
    return cleaned
