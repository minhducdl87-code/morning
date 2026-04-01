#!/usr/bin/env python3
"""Weekly digest generator — runs every Sunday, summarises last 7 daily cards via Gemini."""
import json, os, re
from datetime import datetime, timedelta
from google import genai
from google.genai import types

try:
    import zoneinfo
    tz = zoneinfo.ZoneInfo("Asia/Ho_Chi_Minh")
except ImportError:
    from datetime import timezone
    tz = timezone.utc

MIN_CARDS  = 3   # skip generation if fewer cards available
MAX_WEEKS  = 12  # rolling window for weekly.json

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
now    = datetime.now(tz)

# --- Load last 7 days of cards ---
with open("cards.json", "r", encoding="utf-8") as f:
    all_cards = json.load(f)

cutoff = now - timedelta(days=7)
week_cards = [
    c for c in all_cards
    if datetime.strptime(c["date"], "%Y-%m-%d") >= cutoff.replace(tzinfo=None)
]

if len(week_cards) < MIN_CARDS:
    print(f"Only {len(week_cards)} cards this week (min {MIN_CARDS}) — skipping weekly digest")
    raise SystemExit(0)

from_date = week_cards[-1]["date"]
to_date   = week_cards[0]["date"]

# ISO week number for label
week_num  = now.isocalendar()[1]
week_label = f"Tuần {week_num}/{now.year}"

# --- Compact card context (title + tag + date only to keep prompt small) ---
def compact_cards(cards: list) -> str:
    rows = []
    for c in cards:
        date = c.get("date", "")
        for n in c.get("news", []):
            rows.append(f"[{date}][claude] {n.get('title','')} ({n.get('tag','')})")
        for r in c.get("repos", []):
            rows.append(f"[{date}][repo:{r.get('verdict','')}] {r.get('name','')} — {r.get('desc','')[:60]}")
        for g in c.get("gamingNews", []):
            rows.append(f"[{date}][gaming] {g.get('title','')} ({g.get('tag','')})")
    return "\n".join(rows)

context = compact_cards(week_cards)

PROMPT = f"""Dưới đây là dữ liệu Morning Digest từ {from_date} đến {to_date}:

{context}

Tổng hợp Weekly Digest cho {week_label}. Trả về CHỈ JSON (không markdown):
{{
  "weekLabel": "{week_label}",
  "fromDate": "{from_date}",
  "toDate": "{to_date}",
  "highlights": [
    {{"title":"emoji+tên","desc":"tóm tắt tiếng Việt 2-3 câu, nêu impact","tag":"hot|api|feature|deprecate|model","tagLabel":"🔥 HOT|🔧 API|✨ FEATURE|⏰ DEADLINE|🧠 MODEL"}}
  ],
  "topRepos": [
    {{"name":"owner/repo","url":"https://github.com/owner/repo","desc":"lý do nổi bật tuần này tiếng Việt","stars":"12K+","verdict":"yes"}}
  ],
  "topGaming": [
    {{"title":"emoji+tên","desc":"tóm tắt tiếng Việt","tag":"chart|monet|gameplay|social-casino|casual","tagLabel":"📊 CHART|💰 MONET|🎮 GAMEPLAY|🎰 SOCIAL|🎈 CASUAL"}}
  ]
}}
Rules: highlights 3-5 items (chọn tin quan trọng nhất tuần), topRepos 3 items (verdict=yes, nổi bật nhất), topGaming 2-3 items nếu có data gaming, bỏ qua nếu không có. Tiếng Việt ngắn gọn."""

print(f"Generating weekly digest: {week_label} ({from_date} → {to_date}) from {len(week_cards)} cards...")

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=PROMPT,
    config=types.GenerateContentConfig(temperature=0.4, max_output_tokens=2048)
)

# --- Parse response ---
text = response.text.strip()
text = re.sub(r"^```[a-z]*\n?", "", text)
text = re.sub(r"\n?```$", "", text).strip()

weekly_card = None
try:
    weekly_card = json.loads(text)
except Exception:
    m = re.search(r"\{[\s\S]+\}", text)
    if m:
        try: weekly_card = json.loads(m.group())
        except: pass

if not weekly_card:
    print("Could not parse weekly JSON — skipping")
    raise SystemExit(1)

# --- Update weekly.json (rolling MAX_WEEKS window) ---
try:
    with open("weekly.json", "r", encoding="utf-8") as f:
        weeklies = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    weeklies = []

# Remove existing entry for same week, keep within rolling window
weeklies = [w for w in weeklies if w.get("weekLabel") != week_label]
weeklies.insert(0, weekly_card)
weeklies = weeklies[:MAX_WEEKS]

with open("weekly.json", "w", encoding="utf-8") as f:
    json.dump(weeklies, f, ensure_ascii=False, indent=2)

print(f"Done! {len(weeklies)} weekly digests | "
      f"highlights:{len(weekly_card.get('highlights',[]))} "
      f"repos:{len(weekly_card.get('topRepos',[]))} "
      f"gaming:{len(weekly_card.get('topGaming',[]))}")
