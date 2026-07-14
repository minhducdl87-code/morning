#!/usr/bin/env python3
"""Push daily/recap digest to Telegram channel. Topic-agnostic — reads config.json for section labels."""
import json, os, sys, urllib.request, urllib.parse
from digest_utils import list_item_fields

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
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
    config = {"topics": {}, "site": {}, "telegram": {}}

card       = cards[0]
site       = config.get("site", {})
site_title = site.get("title", "Morning Digest")
topics     = config.get("topics", {})

# Chat ID resolution: env var (comma-sep) > config.telegram.chat_ids > fallback
env_ids = [x.strip() for x in os.environ.get("TELEGRAM_CHAT_IDS", "").split(",") if x.strip()]
config_ids = config.get("telegram", {}).get("chat_ids", []) or []
CHAT_IDS = env_ids or config_ids or ["655323886"]


def section_meta(field: str) -> tuple[str, str]:
    """Return (emoji, section_label) for a field. Fallback: guess from field name."""
    for t in topics.values():
        if t.get("output_field") == field:
            return t.get("emoji", "•"), t.get("section_label", field.capitalize())
    return "•", field.capitalize()


def collect_items(card: dict) -> list[tuple[str, dict]]:
    """Return [(field, item), ...] for all non-repo items with URL, in topic/config order."""
    out = []
    for field in list_item_fields(card):
        for x in card.get(field, []):
            if isinstance(x, dict) and x.get("title") and x.get("url"):
                out.append((field, x))
    return out


def first_items(items: list, n: int = 3) -> list:
    """Take first N items in existing (topic/config) order, deduped by URL.
    NOTE: PRIORITY_TAGS ranking removed — it was stale vs current config.json tags
    (e.g. 'hot' doesn't exist, many tags like 'ai'/'deal'/'gold' fell through to
    default rank 99) and caused a notify loop bug. Simpler + correct: no ranking,
    just take the first N items as they naturally appear."""
    seen, out = set(), []
    for field, x in items:
        if x["url"] in seen:
            continue
        seen.add(x["url"])
        out.append((field, x))
        if len(out) >= n:
            break
    return out


def html_escape(s: str) -> str:
    return (s or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")


def build_morning_message(card: dict) -> str:
    """Full morning digest — sections by topic."""
    lines = [f"{site_title} — <b>{card.get('dateLabel','')}</b> ({card.get('dayLabel','')})", ""]

    all_items = collect_items(card)
    top_picks = first_items(all_items, n=3)
    if top_picks:
        lines.append("🔥 <b>Điểm nhanh sáng nay:</b>")
        for field, x in top_picks:
            emoji, _ = section_meta(field)
            lines.append(f"{emoji} <a href=\"{x['url']}\">{html_escape(x['title'])}</a>")
        lines.append("")

    # Sections per topic (skip if empty)
    for field in list_item_fields(card):
        arr = card.get(field, [])
        if not arr:
            continue
        emoji, label = section_meta(field)
        lines.append(f"{emoji} <b>{html_escape(label)}:</b>")
        for x in arr:
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
    """Shorter 10AM recap — first N items gộp từ các topic (no priority ranking, see first_items)."""
    lines = [f"☕ Recap — <b>{card.get('dateLabel','')}</b>", ""]
    top_picks = first_items(collect_items(card), n=3)
    if not top_picks:
        lines.append("Hôm nay chưa có tin đáng chú ý 😴")
    else:
        for field, x in top_picks:
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

url      = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
TG_LIMIT = 4000   # safety margin under Telegram's 4096-char hard cap per message


def split_message(text: str, limit: int = TG_LIMIT) -> list[str]:
    """Split into <=limit chunks at line boundaries so the full digest never
    exceeds Telegram's 4096 limit (a single oversized sendMessage would fail)."""
    if len(text) <= limit:
        return [text]
    chunks, cur = [], ""
    for line in text.split("\n"):
        while len(line) > limit:            # single over-long line → hard split
            if cur:
                chunks.append(cur); cur = ""
            chunks.append(line[:limit]); line = line[limit:]
        if cur and len(cur) + len(line) + 1 > limit:
            chunks.append(cur); cur = line
        else:
            cur = f"{cur}\n{line}" if cur else line
    if cur:
        chunks.append(cur)
    return chunks


def send_chunk(chat_id: str, text: str) -> bool:
    payload = urllib.parse.urlencode({
        "chat_id":    chat_id,
        "text":       text,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true",
    }).encode()
    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return bool(json.loads(resp.read()).get("ok"))


# Send to every chat_id — split long digests into multiple messages, partial failure OK
chunks = split_message(message)
ok_count = fail_count = 0
for chat_id in CHAT_IDS:
    try:
        if all(send_chunk(chat_id, c) for c in chunks):
            print(f"✓ Sent {MODE} to chat {chat_id} ({len(chunks)} msg)")
            ok_count += 1
        else:
            print(f"✗ chat {chat_id}: Telegram returned not-ok")
            fail_count += 1
    except Exception as e:
        print(f"✗ chat {chat_id}: {e}")
        fail_count += 1

print(f"Total: {ok_count} ok / {fail_count} fail / {len(CHAT_IDS)} recipients")
if ok_count == 0 and fail_count:
    sys.exit(1)
