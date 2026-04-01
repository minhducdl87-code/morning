#!/usr/bin/env python3
"""Send Morning Digest summary to Telegram channel after daily card generation."""
import json, os, sys, urllib.request, urllib.parse

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_IDS  = [cid.strip() for cid in os.environ.get("TELEGRAM_CHAT_ID", "").split(",") if cid.strip()]
PAGE_URL  = "https://minhducdl87-code.github.io/morning"

if not BOT_TOKEN or not CHAT_IDS:
    print("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set — skipping notification")
    sys.exit(0)

# --- Load latest card ---
with open("cards.json", "r", encoding="utf-8") as f:
    cards = json.load(f)

if not cards:
    print("No cards found — skipping notification")
    sys.exit(0)

card = cards[0]

def build_message(card: dict) -> str:
    """Format card data into a concise Telegram message."""
    lines = [f"☀️ *Morning Digest* — {card.get('dateLabel','')} ({card.get('dayLabel','')})", ""]

    # Top 3 Claude news
    news = card.get("news", [])
    if news:
        lines.append("📰 *Claude News:*")
        for item in news[:3]:
            lines.append(f"• {item.get('title','')}")
        lines.append("")

    # Top 3 repos with verdict=yes
    repos = [r for r in card.get("repos", []) if r.get("verdict") == "yes"]
    if repos:
        lines.append("🐙 *GitHub Hot:*")
        for r in repos[:3]:
            reason = r.get("reason", "")
            reason_short = reason[:60] + "…" if len(reason) > 60 else reason
            lines.append(f"• [{r.get('name','')}]({r.get('url','')}) ⭐{r.get('stars','')} — {reason_short}")
        lines.append("")

    # Top 2 gaming news (if present)
    gaming = card.get("gamingNews", [])
    if gaming:
        lines.append("🎮 *Mobile Game:*")
        for item in gaming[:2]:
            lines.append(f"• {item.get('title','')}")
        lines.append("")

    lines.append(f"🔗 {PAGE_URL}")
    return "\n".join(lines)

message = build_message(card)

# --- Send to each Telegram chat ID (stdlib only) ---
url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
errors = []

for chat_id in CHAT_IDS:
    payload = urllib.parse.urlencode({
        "chat_id":    chat_id,
        "text":       message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": "true",
    }).encode()
    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            if result.get("ok"):
                print(f"✓ Sent to chat {chat_id}")
            else:
                err = result.get('description', 'unknown')
                print(f"✗ Telegram API error for {chat_id}: {err}")
                errors.append(chat_id)
    except Exception as e:
        print(f"✗ Failed for {chat_id}: {e}")
        errors.append(chat_id)

if errors:
    print(f"Failed chat IDs: {errors}")
    sys.exit(1)
