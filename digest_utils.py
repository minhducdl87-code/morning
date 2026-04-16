"""Shared utilities for Morning Digest generators."""
from datetime import datetime, timedelta


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
