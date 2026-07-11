#!/usr/bin/env python3
"""Push daily/recap digest to Telegram channel. Topic-agnostic — reads config.json for section labels."""
import json, os, sys, urllib.request, urllib.parse

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID   = "655323886"
PAGE_URL  = "https://minhducdl87-code.github.io/morning"
MODE      = os.environ.get("NOTIFY_MODE", "morning")   # "morning" or "recap"

if not BOT_TOKEN:
    print("TELEGRAM_BOT_TOKEN not set — skipping notification")
    sys.exit(0)

with open("cards.json", "r", encoding="utf-8") as f:
    cards = json.load(f)
if not cards:
    print("No cards found — skipping notification")
    sys.exit(0)

try:
    with open("config.json", "r", encoding="utf-8") as f:
        config = json.load(f)
except FileNotFoundError:
    config = {"topics": {}, "site": {}}

card       = cards[0]
site       = config.get("site", {})
site_title = site.get("title", "Morning Digest")
topics     = config.get("topics", {})

# Priority tags for "Top không thể bỏ qua" section
PRIORITY_TAGS = {"hot":0, "launch":1, "stock":2, "crypto":3, "policy":3, "economy":4, "movie":5, "review":6}


def section_meta(field: str) -> tuple[str, str]:
    """Return (emoji, section_label) for a field. Fallback: guess from field name."""
    for t in topics.values():
        if t.get("output_field") == field:
            return t.get("emoji", "•"), t.get("section_label", field.capitalize())
    return "•", field.capitalize()


def collect_items(card: dict) -> list[tuple[str, dict]]:
    """Return [(field, item), ...] for all non-repo items with URL."""
    out = []
    for field, arr in card.items():
        if not isinstance(arr, list) or field in ("date","dayLabel","dateLabel"):
            continue
        for x in arr:
            if isinstance(x, dict) and x.get("title") and x.get("url"):
                out.append((field, x))
    return out


def rank_top(items: list, n: int = 3) -> list:
    """Sort by priority tag, return top N unique-by-URL."""
    items = sorted(items, key=lambda it: PRIORITY_TAGS.get(it[1].get("tag",""), 99))
    seen, out = set(), []
    for field, x in items:
        if x["url"] in seen: continue
        seen.add(x["url"])
        out.append((field, x))
        if len(out) >= n: break
    return out


def html_escape(s: str) -> str:
    return (s or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")


def build_morning_message(card: dict) -> str:
    """Full morning digest — sections by topic."""
    lines = [f"{site_title} — <b>{card.get('dateLabel','')}</b> ({card.get('dayLabel','')})", ""]

    all_items = collect_items(card)
    top3 = rank_top(all_items, n=3)
    if top3:
        lines.append("🔥 <b>Top 3 không thể bỏ qua:</b>")
        for field, x in top3:
            emoji, _ = section_meta(field)
            lines.append(f"{emoji} <a href=\"{x['url']}\">{html_escape(x['title'])}</a>")
        lines.append("")

    # Sections per topic (skip if empty)
    for field, arr in card.items():
        if field in ("date","dayLabel","dateLabel") or not isinstance(arr, list) or not arr:
            continue
        emoji, label = section_meta(field)
        lines.append(f"{emoji} <b>{html_escape(label)}:</b>")
        for x in arr[:3]:
            title = html_escape(x.get("title") or x.get("name",""))
            url = x.get("url","")
            if url:
                lines.append(f"• <a href=\"{url}\">{title}</a>")
            else:
                lines.append(f"• {title}")
        lines.append("")

    lines.append(f"🔗 {PAGE_URL}")
    return "\n".join(lines)


def build_recap_message(card: dict) -> str:
    """Shorter 10AM recap — just Top 3 with source domain."""
    lines = [f"☕ Recap — <b>{card.get('dateLabel','')}</b>", ""]
    top3 = rank_top(collect_items(card), n=3)
    if not top3:
        lines.append("Hôm nay chưa có tin đáng chú ý 😴")
    else:
        for field, x in top3:
            emoji, _ = section_meta(field)
            url = x["url"]
            domain = url.split("/")[2] if "//" in url else url
            lines.append(f"{emoji} <a href=\"{url}\"><b>{html_escape(x['title'])}</b></a>")
            desc = html_escape(x.get("desc",""))[:180]
            if desc:
                lines.append(f"   {desc}")
            lines.append(f"   <i>({domain})</i>")
            lines.append("")
    lines.append(f"🔗 {PAGE_URL}")
    return "\n".join(lines)


message = build_recap_message(card) if MODE == "recap" else build_morning_message(card)

# Send
url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
payload = urllib.parse.urlencode({
    "chat_id":    CHAT_ID,
    "text":       message,
    "parse_mode": "HTML",
    "disable_web_page_preview": "true",
}).encode()
req = urllib.request.Request(url, data=payload, method="POST")
req.add_header("Content-Type", "application/x-www-form-urlencoded")
try:
    with urllib.request.urlopen(req, timeout=10) as resp:
        result = json.loads(resp.read())
        if result.get("ok"):
            print(f"✓ Sent {MODE} to chat {CHAT_ID}")
        else:
            print(f"✗ Telegram API error: {result.get('description', 'unknown')}")
            sys.exit(1)
except Exception as e:
    print(f"✗ Failed: {e}")
    sys.exit(1)
