"""RSS/Atom feed fetcher — supplements Jina search for VN-specific sources."""
import html
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from jina_fetch import is_blocked_url

DEFAULT_HEADERS = {"User-Agent": "Mozilla/5.0 morning-digest"}
RSS_TIMEOUT    = 10
MAX_PER_FEED   = 8
MAX_AGE_DAYS   = 14  # drop items older than this (stale news guard); unparseable dates are kept


def parse_pub_date(pub: str) -> datetime | None:
    """Parse RSS/Atom pubDate: RFC-822 ('Thu, 23 Jul 2026 09:30:00 +0700'),
    ISO-8601 ('2026-07-23T09:30:00+07:00'), or US-style ('7/23/2026 10:10:00 AM').
    Returns tz-aware datetime (naive → assume UTC) or None if unparseable."""
    pub = (pub or "").strip()
    if not pub:
        return None
    dt = None
    try:
        dt = parsedate_to_datetime(pub)
    except (ValueError, TypeError):
        try:
            dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
        except ValueError:
            # US-style with AM/PM (observed from tuoitre.vn: '7/23/2026 10:10:00 AM').
            # AM/PM marker implies m/d ordering; ambiguous 24h m/d-vs-d/m formats are
            # deliberately NOT parsed → item is kept (fail-open).
            try:
                dt = datetime.strptime(pub, "%m/%d/%Y %I:%M:%S %p")
            except ValueError:
                pass
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def is_stale(pub: str) -> bool:
    """True if pubDate is parseable AND older than MAX_AGE_DAYS."""
    dt = parse_pub_date(pub)
    if dt is None:
        return False  # keep items with unknown dates
    return dt < datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)


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
    stale = 0

    # RSS 2.0
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link  = (item.findtext("link") or "").strip()
        desc  = (item.findtext("description") or "").strip()
        pub   = item.findtext("pubDate") or ""
        if is_stale(pub):
            stale += 1
            continue
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
            if is_stale(pub):
                stale += 1
                continue
            if title and link and not is_blocked_url(link):
                items.append({
                    "title":       strip_cdata(title),
                    "url":         link,
                    "description": strip_cdata(desc)[:400],
                    "pubDate":     pub,
                })
            if len(items) >= max_items:
                break

    print(f"  [rss] {url} → {len(items)} items" + (f" ({stale} stale dropped)" if stale else ""))
    return items


def strip_cdata(s: str) -> str:
    """Strip CDATA wrapper, HTML tags, unescape entities + collapse whitespace."""
    s = s.replace("<![CDATA[", "").replace("]]>", "")
    s = re.sub(r"</?[a-zA-Z][^>]*>", " ", s)  # drop HTML tags only (keep 'a < b > c' text)
    return " ".join(html.unescape(s).split())


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
    lines = ["RSS feed items (URL nguyên xi, pubDate = ngày đăng — ưu tiên tin mới):"]
    for i, r in enumerate(all_items, 1):
        lines.append(f"[R{i}] {r['title']}")
        lines.append(f"    URL: {r['url']}")
        if r.get("pubDate"):
            lines.append(f"    pubDate: {r['pubDate']}")
        if r["description"]:
            lines.append(f"    {r['description'][:300]}")
        lines.append("")
    return "\n".join(lines), valid_urls
