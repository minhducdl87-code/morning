"""URL liveness check (HEAD, parallel) + item validation for Morning Digest.
Split out of digest_utils.py to stay under the 200-LOC file guideline (paired with
dedup_utils.py — digest_utils.py re-exports both as a thin facade)."""
import urllib.request
import urllib.error
import re
import socket
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
    """Return True unless URL is CONFIRMED dead. Benefit-of-doubt policy: many real
    news sites (vnexpress.net etc.) block bot HEAD/GET requests from datacenter IPs
    (e.g. GitHub Actions runners) with 403/405/429 or a timeout — that's a bot-block,
    NOT proof the article is gone, and previously caused false-negative drops of real
    RSS items (entertainment/lifestyle sections wiped to zero). Only treat as dead:
    404/410 (resource confirmed gone) and DNS failure/connection refused (host does
    not exist / nothing listening) — everything else gets the benefit of the doubt."""
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
        if e.code in (404, 410):
            return False
        return True  # 403/405/429/5xx — ambiguous (bot-block/server hiccup), keep it
    except urllib.error.URLError as e:
        reason = e.reason
        if isinstance(reason, socket.gaierror):
            return False  # DNS resolution failed — host doesn't exist
        if isinstance(reason, ConnectionRefusedError):
            return False  # connection actively refused — nothing listening
        return True  # timeout or other transient network error — benefit of doubt
    except TimeoutError:
        return True
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

def validate_news_items(items: list, live_map: dict, trusted_urls: set | None = None) -> list:
    """STRICT: drop news items without live URL. Top rule — news must have real source.
    trusted_urls: real URLs sourced directly from RSS/Jina/GitHub fetch layer (not
    LLM-generated) — these bypass the HEAD-check live_map entirely since we already
    know they're real, avoiding false-negative drops when a source blocks bot checks."""
    trusted_urls = trusted_urls or set()
    cleaned = []
    for n in items:
        url = (n.get("url") or "").strip()
        if not url:
            print(f"  [validate] dropped news (no URL): {n.get('title','')[:60]}")
            continue
        if url in trusted_urls:
            cleaned.append(n)
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
