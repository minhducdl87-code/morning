#!/usr/bin/env python3
"""Daily morning digest generator — reads config.json for topics, calls Gemini, updates cards.json."""
import json, os, re
from datetime import datetime, timedelta
from google import genai
from google.genai import types
from digest_utils import get_recent_titles, get_recent_urls, validate_news_urls, validate_repo_urls
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

# --- Load existing cards for dedup context ---
with open("cards.json", "r", encoding="utf-8") as f:
    cards = json.load(f)

recent_titles = get_recent_titles(cards, date_str, now, days=3)
recent_urls   = get_recent_urls(cards, date_str, now, days=3)


def build_prompt(topics: dict, recent_titles: list, topic_contexts: dict) -> str:
    """Build Gemini prompt with pre-fetched context. Hard rules prevent URL hallucination."""
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
            # Critical: do NOT tell Gemini to invent. Allow Google Search grounding fallback.
            lines.append("(Không có dữ liệu tìm kiếm. Nếu được cấp Google Search tool, dùng nó. Nếu không, trả về mảng rỗng [].)")

        lines.append(f'Trả về field "{field}" với {min_i}-{max_i} items, schema mỗi item: {schema}\n')
        schema_fields += f',"{field}":[...]'

    if recent_titles:
        lines.append("TRÁNH lặp lại — các tin sau đã xuất hiện trong 3 ngày qua, KHÔNG đưa vào:")
        for t in recent_titles[:15]:
            lines.append(f"  - {t}")
        lines.append("")

    lines.append("Trả về CHỈ JSON (không markdown, không text thêm):")
    lines.append("{" + schema_fields + "}")
    lines.append("")
    lines.append("HARD RULES (BẮT BUỘC):")
    lines.append("1. URL CHỈ được lấy từ 'Dữ liệu tìm kiếm' / 'Dữ liệu GitHub' / Google Search citations. KHÔNG bịa, KHÔNG sửa, KHÔNG đoán.")
    lines.append("2. Nếu không có URL thật cho 1 item → set \"url\":\"\" (chuỗi rỗng), KHÔNG copy schema text như 'https://link-...'")
    lines.append("3. Repo: name + url + stars phải khớp DỮ LIỆU GITHUB nguyên văn. KHÔNG tạo repo mới.")
    lines.append("4. Nếu data ít hơn min_items → trả số ít hơn, KHÔNG bịa thêm để đủ.")
    lines.append("5. Tiếng Việt ngắn gọn dễ hiểu. Trả về ĐẦY ĐỦ tất cả các field.")

    return "\n".join(lines)


# --- Step 1: Fetch web content ---
print(f"Generating card for {date_str} | topics: {list(topics.keys())}...")
print("Step 1: Fetching web content...")

topic_contexts = {}
valid_urls_per_topic = {}
for key, topic in topics.items():
    ctx, urls = fetch_topic_context(topic, month_year)
    topic_contexts[key] = ctx
    valid_urls_per_topic[key] = urls

all_valid_urls = set().union(*valid_urls_per_topic.values())
has_data = bool(all_valid_urls)
print(f"Fetch done. Total URLs in whitelist: {len(all_valid_urls)}")

# --- Step 2: Build prompt and call Gemini ---
PROMPT = build_prompt(topics, recent_titles, topic_contexts)
print(f"Step 2: Calling Gemini... (prompt: {len(PROMPT)} chars)")


def call_gemini(prompt, retries=2, use_search=False):
    """Call Gemini with retry. Returns (text, grounding_urls). use_search enables Google Search."""
    tools = [types.Tool(google_search=types.GoogleSearch())] if use_search else []
    for attempt in range(retries + 1):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=tools,
                    temperature=0.3,
                    max_output_tokens=8192,
                    thinking_config=types.ThinkingConfig(thinking_budget=2048),
                )
            )

            text_parts = []
            grounding_urls = set()
            if response.candidates:
                cand = response.candidates[0]
                for part in (cand.content.parts or []):
                    if hasattr(part, 'thought') and part.thought:
                        continue
                    if hasattr(part, 'text') and part.text:
                        text_parts.append(part.text)
                # Extract grounding citations (real source URLs from Google Search)
                gm = getattr(cand, 'grounding_metadata', None)
                if gm:
                    for chunk in (getattr(gm, 'grounding_chunks', None) or []):
                        web = getattr(chunk, 'web', None)
                        if web and getattr(web, 'uri', None):
                            grounding_urls.add(web.uri)

            text = "\n".join(text_parts).strip()
            if text:
                print(f"  Attempt {attempt+1}: got {len(text)} chars, {len(grounding_urls)} citations")
                return text, grounding_urls

            finish = "unknown"
            if response.candidates:
                finish = str(response.candidates[0].finish_reason)
            print(f"  Attempt {attempt+1}: empty. Finish: {finish}")

        except Exception as e:
            print(f"  Attempt {attempt+1} error: {e}")

    return None, set()


# Try without Google Search (Jina/GitHub context), fallback to Google Search if no data
text, citations = call_gemini(PROMPT, use_search=False)
if not text or not has_data:
    print("Falling back to Gemini + Google Search grounding...")
    text2, citations2 = call_gemini(PROMPT, retries=1, use_search=True)
    if text2:
        text = text2
        citations |= citations2

# Merge citations into URL whitelist
all_valid_urls |= citations
print(f"Final URL whitelist size: {len(all_valid_urls)}")

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

# --- URL validation: drop fake URLs / fake repos ---
print("Step 3: Validating URLs...")
card_json["news"]       = validate_news_urls(card_json.get("news", []),       all_valid_urls)
card_json["gamingNews"] = validate_news_urls(card_json.get("gamingNews", []), all_valid_urls)
card_json["repos"]      = validate_repo_urls(card_json.get("repos", []),      valid_urls_per_topic.get("github_trending", set()))

# --- Dedup news by URL against last 3 days ---
if recent_urls:
    before_news   = len(card_json.get("news", []))
    before_gaming = len(card_json.get("gamingNews", []))
    card_json["news"]       = [n for n in card_json.get("news", [])       if not n.get("url") or n["url"] not in recent_urls]
    card_json["gamingNews"] = [g for g in card_json.get("gamingNews", []) if not g.get("url") or g["url"] not in recent_urls]
    removed = (before_news - len(card_json["news"])) + (before_gaming - len(card_json["gamingNews"]))
    if removed:
        print(f"Dedup removed {removed} duplicate item(s) found in last 3 days")

# --- Update cards.json (rolling 30-day window) ---
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
