"""Jina Search API utility for Morning Digest."""
import json, os, urllib.request, urllib.parse

JINA_API_KEY = os.environ.get("JINA_API_KEY", "")
SEARCH_URL = "https://s.jina.ai/"


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


def fetch_topic_context(topic: dict, month_year: str) -> str:
    """Fetch search results for a topic's queries, return as text context."""
    all_results = []
    for q in topic["search_queries"]:
        query = q.replace("{month_year}", month_year)
        results = jina_search(query)
        all_results.extend(results)

    if not all_results:
        return ""

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
    return "\n".join(lines)
