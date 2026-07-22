"""RSS/Atom feed fetcher — supplements Jina search for VN-specific sources."""
import urllib.request
import xml.etree.ElementTree as ET
from jina_fetch import is_blocked_url

DEFAULT_HEADERS = {"User-Agent": "Mozilla/5.0 morning-digest"}
RSS_TIMEOUT    = 10
MAX_PER_FEED   = 8


def fetch_rss(url: str, max_items: int = MAX_PER_FEED) -> list[dict]:
    """Fetch RSS 2.0 or Atom feed. Returns [{title, url, description, pubDate}]."""
    req = urllib.request.Request(url, headers=DEFAULT_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=RSS_TIMEOUT) as resp:
            data = resp.read()
    except Exception as e:
        print(f"  [rss] Fetch error {url}: {e}")
        return []

    try:
        root = ET.fromstring(data)
    except ET.ParseError as e:
        print(f"  [rss] Parse error {url}: {e}")
        return []

    items = []

    # RSS 2.0
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link  = (item.findtext("link") or "").strip()
        desc  = (item.findtext("description") or "").strip()
        pub   = item.findtext("pubDate") or ""
        if title and link and not is_blocked_url(link):
            items.append({
                "title":       strip_cdata(title),
                "url":         link,
                "description": strip_cdata(desc)[:400],
                "pubDate":     pub,
            })
        if len(items) >= max_items:
            break

    # Atom fallback
    if not items:
        ns = "{http://www.w3.org/2005/Atom}"
        for entry in root.iter(ns+"entry"):
            title = (entry.findtext(ns+"title") or "").strip()
            link_el = entry.find(ns+"link")
            link = link_el.get("href") if link_el is not None else ""
            desc = (entry.findtext(ns+"summary") or entry.findtext(ns+"content") or "").strip()
            pub  = entry.findtext(ns+"published") or entry.findtext(ns+"updated") or ""
            if title and link and not is_blocked_url(link):
                items.append({
                    "title":       strip_cdata(title),
                    "url":         link,
                    "description": strip_cdata(desc)[:400],
                    "pubDate":     pub,
                })
            if len(items) >= max_items:
                break

    print(f"  [rss] {url} → {len(items)} items")
    return items


def strip_cdata(s: str) -> str:
    """Strip CDATA wrapper + collapse whitespace."""
    s = s.replace("<![CDATA[", "").replace("]]>", "")
    return " ".join(s.split())


def fetch_rss_topic(topic: dict) -> tuple[str, set[str]]:
    """Aggregate all RSS feeds for a topic. Returns (text_context, valid_urls)."""
    feeds = topic.get("rss_feeds") or []
    if not feeds:
        return "", set()

    all_items = []
    for url in feeds:
        all_items.extend(fetch_rss(url))

    if not all_items:
        return "", set()

    valid_urls = {r["url"] for r in all_items if r.get("url")}
    lines = ["RSS feed items (URL nguyên xi):"]
    for i, r in enumerate(all_items, 1):
        lines.append(f"[R{i}] {r['title']}")
        lines.append(f"    URL: {r['url']}")
        if r["description"]:
            lines.append(f"    {r['description'][:300]}")
        lines.append("")
    return "\n".join(lines), valid_urls
