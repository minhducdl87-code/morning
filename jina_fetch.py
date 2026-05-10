"""Web fetching utilities for Morning Digest: Jina Search + GitHub Trending API."""
import json, os, urllib.request, urllib.parse
from datetime import datetime, timedelta

JINA_API_KEY = os.environ.get("JINA_API_KEY", "")
SEARCH_URL   = "https://s.jina.ai/"
GITHUB_API   = "https://api.github.com/search/repositories"


# ── Jina Search ──────────────────────────────────────────────────────────────

def jina_search(query: str, max_results: int = 5) -> list[dict]:
    """Search via Jina Search API. Returns list of {title, url, description, content}."""
    if not JINA_API_KEY:
        print(f"  [jina] No API key, skipping: {query}")
        return []

    url = SEARCH_URL + urllib.parse.quote(query)
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {JINA_API_KEY}")
    req.add_header("Accept", "application/json")
    req.add_header("X-With-Generated-Alt", "false")

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        results = data.get("data", [])[:max_results]
        print(f"  [jina] '{query}' → {len(results)} results")
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "description": r.get("description", ""),
                "content": (r.get("content", "") or "")[:1500],
            }
            for r in results
        ]
    except Exception as e:
        print(f"  [jina] Error for '{query}': {e}")
        return []


def fetch_jina_topic(topic: dict, month_year: str) -> tuple[str, set[str]]:
    """Fetch Jina results for a topic. Returns (text_context, valid_urls_set)."""
    all_results = []
    for q in topic.get("search_queries", []):
        query = q.replace("{month_year}", month_year)
        all_results.extend(jina_search(query))

    if not all_results:
        return "", set()

    valid_urls = {r["url"] for r in all_results if r.get("url")}
    lines = []
    for i, r in enumerate(all_results, 1):
        lines.append(f"[{i}] {r['title']}")
        lines.append(f"    URL: {r['url']}")
        if r["description"]:
            lines.append(f"    {r['description']}")
        if r["content"]:
            snippet = r["content"][:500].replace("\n", " ")
            lines.append(f"    Content: {snippet}")
        lines.append("")
    return "\n".join(lines), valid_urls


# ── GitHub Trending API ──────────────────────────────────────────────────────

def github_search(query: str, max_results: int = 8) -> list[dict]:
    """Search GitHub repos via public Search API (no auth needed for low volume)."""
    params = urllib.parse.urlencode({
        "q":        query,
        "sort":     "stars",
        "order":    "desc",
        "per_page": max_results,
    })
    url = f"{GITHUB_API}?{params}"
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "morning-digest")

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        items = data.get("items", [])[:max_results]
        print(f"  [github] '{query}' → {len(items)} repos")
        return [
            {
                "name":  it.get("full_name", ""),
                "url":   it.get("html_url", ""),
                "desc":  it.get("description") or "",
                "stars": format_stars(it.get("stargazers_count", 0)),
                "lang":  it.get("language") or "",
            }
            for it in items
        ]
    except Exception as e:
        print(f"  [github] Error for '{query}': {e}")
        return []


def format_stars(n: int) -> str:
    """Format star count: 1234 → '1.2K', 12345 → '12K+'."""
    if n >= 1000:
        return f"{n/1000:.1f}K".rstrip("0").rstrip(".") + "+"
    return str(n)


def fetch_github_topic(topic: dict, cutoff_date: str) -> tuple[str, set[str]]:
    """Fetch GitHub repos for github_trending topic. Returns (text_context, valid_urls_set)."""
    seen = {}
    for q in topic.get("github_queries", []):
        query = q.replace("{cutoff_date}", cutoff_date)
        for repo in github_search(query):
            if repo["url"] and repo["url"] not in seen:
                seen[repo["url"]] = repo

    if not seen:
        return "", set()

    valid_urls = set(seen.keys())
    lines = ["Dữ liệu GitHub (chỉ chọn repo từ list này, KHÔNG bịa thêm):"]
    for i, r in enumerate(seen.values(), 1):
        lines.append(f"[{i}] {r['name']}  ⭐ {r['stars']}  ({r['lang']})")
        lines.append(f"    URL: {r['url']}")
        if r["desc"]:
            lines.append(f"    Desc: {r['desc'][:200]}")
        lines.append("")
    return "\n".join(lines), valid_urls


# ── Dispatcher ────────────────────────────────────────────────────────────────

def fetch_topic_context(topic: dict, month_year: str) -> tuple[str, set[str]]:
    """Dispatch to fetcher based on topic.data_source. Returns (text_context, valid_urls)."""
    source = topic.get("data_source", "jina")
    if source == "github_api":
        cutoff = (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d")
        return fetch_github_topic(topic, cutoff)
    return fetch_jina_topic(topic, month_year)
