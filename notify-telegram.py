#!/usr/bin/env python3
"""Send Morning Digest summary to Telegram channel after daily card generation."""
import json, os, sys, urllib.request, urllib.parse

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID   = "655323886"
PAGE_URL  = "https://minhducdl87-code.github.io/morning"

if not BOT_TOKEN:
    print("TELEGRAM_BOT_TOKEN not set — skipping notification")
    sys.exit(0)

# --- Load latest card ---
with open("cards.json", "r", encoding="utf-8") as f:
    cards = json.load(f)

if not cards:
    print("No cards found — skipping notification")
    sys.exit(0)

card = cards[0]

def build_message(card: dict) -> str:
    """Format card data into a concise Telegram message (HTML)."""
    lines = [f"☀️ <b>Morning Digest</b> — {card.get('dateLabel','')} ({card.get('dayLabel','')})", ""]

    # Top 3 Claude news
    news = card.get("news", [])
    if news:
        lines.append("📰 <b>Claude News:</b>")
        for item in news[:3]:
            lines.append(f"• {item.get('title','')}")
        lines.append("")

    # Top 3 repos with verdict=yes
    repos = [r for r in card.get("repos", []) if r.get("verdict") == "yes"]
    if repos:
        lines.append("🐙 <b>GitHub Hot:</b>")
        for r in repos[:3]:
            reason = r.get("reason", "")
            reason_short = reason[:60] + "…" if len(reason) > 60 else reason
            lines.append(f"• <a href=\"{r.get('url','')}\">{r.get('name','')}</a> ⭐{r.get('stars','')} — {reason_short}")
        lines.append("")

    # Top 2 gaming news (if present)
    gaming = card.get("gamingNews", [])
    if gaming:
        lines.append("🎮 <b>Mobile Game:</b>")
        for item in gaming[:2]:
            lines.append(f"• {item.get('title','')}")
        lines.append("")

    lines.append(f"🔗 {PAGE_URL}")
    return "\n".join(lines)

message = build_message(card)

# --- Send to Telegram ---
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
            print(f"✓ Sent to chat {CHAT_ID}")
        else:
            print(f"✗ Telegram API error: {result.get('description', 'unknown')}")
            sys.exit(1)
except Exception as e:
    print(f"✗ Failed: {e}")
    sys.exit(1)
