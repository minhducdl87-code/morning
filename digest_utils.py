"""Shared utilities for Morning Digest generators."""
import re
from datetime import datetime, timedelta

GITHUB_REPO_RE = re.compile(r"^https://github\.com/[^/\s]+/[^/\s]+/?$")


def get_recent_titles(cards: list, date_str: str, now, days: int = 3) -> list:
    """Extract news/gaming titles from last N days (excluding today) for dedup prompt injection."""
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
            titles += [n["title"] for n in c.get("news", [])       if n.get("title")]
            titles += [g["title"] for g in c.get("gamingNews", []) if g.get("title")]
    return titles


def get_recent_urls(cards: list, date_str: str, now, days: int = 3) -> set:
    """Extract news/gaming URLs from last N days for post-processing URL dedup."""
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
            urls |= {n["url"] for n in c.get("news", [])       if n.get("url")}
            urls |= {g["url"] for g in c.get("gamingNews", []) if g.get("url")}
    return urls - {""}


def validate_news_urls(items: list, valid_urls: set) -> list:
    """Clear URL on news items if not in whitelist. Drops obvious schema-leak placeholders."""
    cleaned = []
    for n in items:
        url = (n.get("url") or "").strip()
        if url:
            # Drop schema literal leaks (e.g. "https://link-hoặc-chuỗi-rỗng")
            if "link-ho" in url or " " in url or not url.startswith("http"):
                n["url"] = ""
            elif url not in valid_urls:
                print(f"  [validate] news URL not in whitelist, clearing: {url}")
                n["url"] = ""
        cleaned.append(n)
    return cleaned


def validate_repo_urls(items: list, valid_urls: set) -> list:
    """Drop repo items whose URL doesn't match github.com/owner/repo or isn't in whitelist."""
    cleaned = []
    for r in items:
        url = (r.get("url") or "").strip()
        if not GITHUB_REPO_RE.match(url):
            print(f"  [validate] dropped repo (bad URL format): {url}")
            continue
        if valid_urls and url not in valid_urls:
            print(f"  [validate] dropped repo (not in whitelist): {url}")
            continue
        cleaned.append(r)
    return cleaned
