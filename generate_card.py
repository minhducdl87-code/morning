#!/usr/bin/env python3
"""Daily morning digest generator — reads config.json for topics, calls Gemini, updates cards.json."""
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

client     = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
now        = datetime.now(tz)
day_names  = ["Thứ Hai","Thứ Ba","Thứ Tư","Thứ Năm","Thứ Sáu","Thứ Bảy","Chủ Nhật"]
date_str   = now.strftime("%Y-%m-%d")
date_label = now.strftime("%d/%m/%Y")
day_label  = day_names[now.weekday()]
month_year = now.strftime("%B %Y")

# --- Load topic config ---
with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)
topics = {k: v for k, v in config["topics"].items() if v.get("enabled", True)}

def build_prompt(topics: dict) -> str:
    """Build dynamic Gemini prompt based on enabled topics in config."""
    lines = [f"Hôm nay là {day_label}, {date_label}.",
             "Dùng Google Search tìm kiếm và tổng hợp morning digest. Thực hiện các task sau:\n"]

    # Build output schema dynamically — only include enabled topics
    schema_fields = f'"date":"{date_str}","dayLabel":"{day_label}","dateLabel":"{date_label}"'

    for i, (key, topic) in enumerate(topics.items(), start=1):
        queries = " và ".join(
            f'"{q.replace("{month_year}", month_year)}"' for q in topic["search_queries"]
        )
        field   = topic["output_field"]
        min_i   = topic["min_items"]
        max_i   = topic["max_items"]
        instr   = topic["prompt_instruction"]
        schema  = topic["schema"]

        lines.append(f"TASK {i}: Search {queries}")
        lines.append(f"{instr}")
        lines.append(f"Trả về field \"{field}\" với {min_i}-{max_i} items, schema mỗi item: {schema}\n")

        schema_fields += f',"{field}":[...]'

    lines.append("Trả về CHỈ JSON (không markdown, không text thêm):")
    lines.append("{" + schema_fields + "}")
    lines.append("Rules: tiếng Việt ngắn gọn dễ hiểu. BẮT BUỘC trả về ĐẦY ĐỦ tất cả các field trong schema, KHÔNG được bỏ sót field nào.")
    return "\n".join(lines)

PROMPT = build_prompt(topics)
print(f"Generating card for {date_str} | topics: {list(topics.keys())}...")

def call_gemini(prompt, retries=2):
    """Call Gemini with retry, extract text from all response parts."""
    for attempt in range(retries + 1):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                    temperature=0.5,
                    max_output_tokens=4096,
                )
            )
            # Extract text from all parts (response.text can be None with grounding)
            text_parts = []
            if response.candidates:
                for part in (response.candidates[0].content.parts or []):
                    if part.text:
                        text_parts.append(part.text)
            text = "\n".join(text_parts).strip()
            if text:
                return text
            print(f"Attempt {attempt+1}: empty response. Finish reason: {response.candidates[0].finish_reason if response.candidates else 'no candidates'}")
        except Exception as e:
            print(f"Attempt {attempt+1} error: {e}")
    return None

text = call_gemini(PROMPT)

# --- Parse JSON response ---
if not text:
    print("All attempts failed. Using fallback card.")
    card_json = {"date": date_str, "dayLabel": day_label, "dateLabel": date_label,
                 "news": [], "repos": [], "gamingNews": []}
else:
    text = text.strip()
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
        print("Could not parse JSON, using fallback")
        card_json = {"date": date_str, "dayLabel": day_label, "dateLabel": date_label,
                     "news": [], "repos": [], "gamingNews": []}

# --- Update cards.json (rolling 30-day window) ---
with open("cards.json", "r", encoding="utf-8") as f:
    cards = json.load(f)

cards = [c for c in cards if c.get("date") != date_str]
cutoff = now - timedelta(days=30)
cards = [c for c in cards if datetime.strptime(c["date"], "%Y-%m-%d") >= cutoff.replace(tzinfo=None)]
cards.insert(0, card_json)

with open("cards.json", "w", encoding="utf-8") as f:
    json.dump(cards, f, ensure_ascii=False, indent=2)

print(f"Done! {len(cards)} cards | "
      f"news:{len(card_json.get('news',[]))} "
      f"repos:{len(card_json.get('repos',[]))} "
      f"gaming:{len(card_json.get('gamingNews',[]))}")
