"""URL liveness check (HEAD, parallel) + item validation for Morning Digest.
Split out of digest_utils.py to stay under the 200-LOC file guideline (paired with
dedup_utils.py — digest_utils.py re-exports both as a thin facade)."""
import urllib.request
import urllib.error
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

GITHUB_REPO_RE = re.compile(r"^https://github\.com/[^/\s]+/[^/\s]+/?$")
HTTP_TIMEOUT   = 5
HEAD_WORKERS   = 8

# Domains we consider "not a real source" — short-lived redirects, schema leaks
URL_BLACKLIST  = (
    "vertexaisearch.cloud.google.com",  # Gemini grounding redirect with expiring token
    "link-ho",                           # schema literal leak ("link-hoặc-...")
)


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
