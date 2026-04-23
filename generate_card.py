#!/usr/bin/env python3
"""Daily morning digest generator — reads config.json for topics, calls Gemini, updates cards.json."""
import json, os, re
from datetime import datetime, timedelta
from google import genai
from google.genai import types
from digest_utils import get_recent_titles, get_recent_urls
from jina_fetch import fetch_topic_context

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

# --- Load existing cards for dedup context (before building prompt) ---
with open("cards.json", "r", encoding="utf-8") as f:
    cards = json.load(f)

recent_titles = get_recent_titles(cards, date_str, now, days=3)
recent_urls   = get_recent_urls(cards, date_str, now, days=3)

def build_prompt(topics: dict, recent_titles: list, topic_contexts: dict) -> str:
    """Build Gemini prompt with pre-fetched Jina context."""
    lines = [
        f"Hôm nay là {day_label}, {date_label}.",
        "Dựa trên dữ liệu tìm kiếm bên dưới, tổng hợp morning digest.\n"
    ]

    schema_fields = f'"date":"{date_str}","dayLabel":"{day_label}","dateLabel":"{date_label}"'

    for i, (key, topic) in enumerate(topics.items(), start=1):
        field   = topic["output_field"]
        min_i   = topic["min_items"]
        max_i   = topic["max_items"]
        instr   = topic["prompt_instruction"]
        schema  = topic["schema"]

        lines.append(f"── TASK {i}: {key} ──")
        lines.append(instr)

        ctx = topic_contexts.get(key, "")
        if ctx:
            lines.append(f"Dữ liệu tìm kiếm:\n{ctx}")
        else:
            lines.append("(Không có dữ liệu tìm kiếm — tự tổng hợp từ kiến thức.)")

        lines.append(f'Trả về field "{field}" với {min_i}-{max_i} items, schema mỗi item: {schema}\n')
        schema_fields += f',"{field}":[...]'

    if recent_titles:
        lines.append("TRÁNH lặp lại — các tin sau đã xuất hiện trong 3 ngày qua, KHÔNG đưa vào:")
        for t in recent_titles[:15]:
            lines.append(f"  - {t}")
        lines.append("")

    lines.append("Trả về CHỈ JSON (không markdown, không text thêm):")
    lines.append("{" + schema_fields + "}")
    lines.append("Rules: tiếng Việt ngắn gọn dễ hiểu. BẮT BUỘC trả về ĐẦY ĐỦ tất cả các field.")

    return "\n".join(lines)


# --- Step 1: Fetch web content via Jina ---
print(f"Generating card for {date_str} | topics: {list(topics.keys())}...")
print("Step 1: Fetching web content via Jina...")

topic_contexts = {}
for key, topic in topics.items():
    ctx = fetch_topic_context(topic, month_year)
    topic_contexts[key] = ctx

has_jina = any(topic_contexts.values())
print(f"Jina fetch done. Has context: {has_jina}")

# --- Step 2: Build prompt and call Gemini ---
PROMPT = build_prompt(topics, recent_titles, topic_contexts)
print(f"Step 2: Calling Gemini... (prompt: {len(PROMPT)} chars)")


def call_gemini(prompt, retries=2, use_search=False):
    """Call Gemini with retry. use_search=True enables Google Search as fallback."""
    tools = [types.Tool(google_search=types.GoogleSearch())] if use_search else []
    for attempt in range(retries + 1):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=tools,
                    temperature=0.5,
                    max_output_tokens=8192,
                    thinking_config=types.ThinkingConfig(thinking_budget=2048),
                )
            )

            text_parts = []
            if response.candidates:
                for part in (response.candidates[0].content.parts or []):
                    if hasattr(part, 'thought') and part.thought:
                        continue
                    if hasattr(part, 'text') and part.text:
                        text_parts.append(part.text)

            text = "\n".join(text_parts).strip()
            if text:
                print(f"  Attempt {attempt+1}: got {len(text)} chars")
                return text

            finish = "unknown"
            if response.candidates:
                finish = str(response.candidates[0].finish_reason)
            print(f"  Attempt {attempt+1}: empty. Finish: {finish}")

        except Exception as e:
            print(f"  Attempt {attempt+1} error: {e}")

    return None


# Try without Google Search first (Jina context), fallback to Google Search
text = call_gemini(PROMPT, use_search=False)
if not text and not has_jina:
    print("Jina had no data and Gemini failed — retrying with Google Search grounding...")
    text = call_gemini(PROMPT, retries=1, use_search=True)

# --- Parse JSON response ---
if not text:
    print("All attempts failed. Using fallback card.")
    card_json = {
        "date": date_str, "dayLabel": day_label, "dateLabel": date_label,
        "news": [], "repos": [], "gamingNews": []
    }
else:
    print(f"Raw response preview: {text[:300]}...")
    text = text.strip()
    text = re.sub(r"^```[a-z]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text).strip()

    card_json = None
    try:
        card_json = json.loads(text)
    except Exception as e1:
        print(f"Direct JSON parse failed: {e1}")
        # Try to extract JSON block from response
        m = re.search(r"\{[\s\S]+\}", text)
        if m:
            try:
                card_json = json.loads(m.group())
            except Exception as e2:
                print(f"Regex JSON parse also failed: {e2}")

    if not card_json:
        print("Could not parse JSON, using fallback")
        card_json = {
            "date": date_str, "dayLabel": day_label, "dateLabel": date_label,
            "news": [], "repos": [], "gamingNews": []
        }

# Ensure required date fields exist
card_json.setdefault("date", date_str)
card_json.setdefault("dayLabel", day_label)
card_json.setdefault("dateLabel", date_label)

# --- Post-process: dedup news by URL against last 3 days ---
if recent_urls:
    before_news   = len(card_json.get("news", []))
    before_gaming = len(card_json.get("gamingNews", []))
    card_json["news"]       = [n for n in card_json.get("news", [])       if n.get("url", "") not in recent_urls]
    card_json["gamingNews"] = [g for g in card_json.get("gamingNews", []) if g.get("url", "") not in recent_urls]
    removed = (before_news - len(card_json["news"])) + (before_gaming - len(card_json["gamingNews"]))
    if removed:
        print(f"Dedup removed {removed} duplicate item(s) found in last 3 days")

# --- Update cards.json (rolling 30-day window) ---
# cards already loaded above for dedup context — reuse it
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
