#!/usr/bin/env python3
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

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
now        = datetime.now(tz)
day_names  = ["Thứ Hai","Thứ Ba","Thứ Tư","Thứ Năm","Thứ Sáu","Thứ Bảy","Chủ Nhật"]
date_str   = now.strftime("%Y-%m-%d")
date_label = now.strftime("%d/%m/%Y")
day_label  = day_names[now.weekday()]

PROMPT = f"""Hôm nay là {day_label}, {date_label}.
Dùng Google Search tìm kiếm và tổng hợp morning digest. Thực hiện 2 task:

TASK 1: Search "Anthropic Claude news {now.strftime('%B %Y')}" và "Claude API changelog site:anthropic.com"
Lấy tin có IMPACT THỰC TẾ trong 24-48h: model mới, feature mới, breaking change, deadline deprecation.

TASK 2: Search "github trending claude anthropic AI tools this week"
Ưu tiên: Claude tools, MCP servers, agent automation, game dev AI tools.

Trả về CHỈ JSON (không markdown, không text thêm):
{{"date":"{date_str}","dayLabel":"{day_label}","dateLabel":"{date_label}",
"news":[{{"title":"emoji+tên","desc":"mô tả tiếng Việt max 2 câu","tag":"hot|api|feature|deprecate|model","tagLabel":"🔥 HOT|🔧 API|✨ FEATURE|⏰ DEADLINE|🧠 MODEL","source":"ngày·nguồn"}}],
"repos":[{{"name":"owner/repo","url":"https://github.com/owner/repo","desc":"1 câu tiếng Việt","stars":"12K+","verdict":"yes|maybe|skip","reason":"lý do ngắn cho game developer"}}]}}
Rules: news 3-6 items, repos 4-8 items, tiếng Việt ngắn gọn dễ hiểu."""

print(f"🔍 Generating card for {date_str}...")

response = client.models.generate_content(
    model="gemini-2.0-flash",
    contents=PROMPT,
    config=types.GenerateContentConfig(
        tools=[types.Tool(google_search=types.GoogleSearch())],
        temperature=0.5,
    )
)

text = response.text.strip()
text = re.sub(r"^```[a-z]*\n?", "", text)
text = re.sub(r"\n?```$", "", text).strip()

card_json = None
try:
    card_json = json.loads(text)
except Exception:
    m = re.search(r"\{[\s\S]+\}", text)
    if m:
        try: card_json = json.loads(m.group())
        except: pass

if not card_json:
    print("⚠️ Could not parse JSON, using fallback")
    card_json = {"date":date_str,"dayLabel":day_label,"dateLabel":date_label,"news":[],"repos":[]}

with open("cards.json","r",encoding="utf-8") as f:
    cards = json.load(f)
cards = [c for c in cards if c.get("date") != date_str]
cutoff = now - timedelta(days=30)
cards = [c for c in cards if datetime.strptime(c["date"],"%Y-%m-%d") >= cutoff.replace(tzinfo=None)]
cards.insert(0, card_json)
with open("cards.json","w",encoding="utf-8") as f:
    json.dump(cards, f, ensure_ascii=False, indent=2)
print(f"✅ Done! {len(cards)} cards | news:{len(card_json.get('news',[]))} repos:{len(card_json.get('repos',[]))}")