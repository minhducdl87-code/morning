#!/usr/bin/env python3
"""Daily morning digest generator — reads config.json for topics, calls Gemini, updates cards.json."""
import json, os, re
from datetime import datetime, timedelta
from google import genai
from google.genai import types
from digest_utils import get_recent_titles, get_recent_urls, batch_check_urls, validate_news_items, validate_repo_items
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


def build_prompt(topics: dict, recent_titles: list, topic_contexts: dict, tone_guidance: str = "") -> str:
    """Build Gemini prompt with pre-fetched context. Hard rules prevent URL hallucination."""
    lines = [
        f"Hôm nay là {day_label}, {date_label}.",
        "Dựa trên dữ liệu tìm kiếm bên dưới, tổng hợp morning digest.\n"
    ]
    if tone_guidance:
        lines.append(tone_guidance)
        lines.append("")

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
    lines.append("1. URL phải là URL THẬT, kiểm chứng được (sẽ được HEAD-check sau). KHÔNG bịa pattern plausible.")
    lines.append("2. Ưu tiên URL từ 'Dữ liệu tìm kiếm' / 'Dữ liệu GitHub' / Google Search citations.")
    lines.append("3. Nếu không chắc URL → set \"url\":\"\" (chuỗi rỗng) hơn là đoán. Item vẫn hiển thị với title+desc.")
    lines.append("4. Repo: name + url + stars phải khớp DỮ LIỆU GITHUB nguyên văn. KHÔNG tạo repo mới.")
    lines.append("5. Tiếng Việt ngắn gọn dễ hiểu. Trả về ĐẦY ĐỦ tất cả các field. Min_items là goal, không phải buộc — thà ít mà đúng.")

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
PROMPT = build_prompt(topics, recent_titles, topic_contexts, config.get("tone_guidance", ""))
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

# Determine output fields from config (dynamic — supports any topic set)
OUTPUT_FIELDS = [t["output_field"] for t in topics.values() if t.get("output_field")]
REPO_FIELDS   = [t["output_field"] for t in topics.values() if t.get("data_source") == "github_api"]

def empty_card():
    c = {"date": date_str, "dayLabel": day_label, "dateLabel": date_label}
    for f in OUTPUT_FIELDS:
        c[f] = []
    return c

# --- Parse JSON response ---
if not text:
    print("All attempts failed. Using fallback card.")
    card_json = empty_card()
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
        card_json = empty_card()

# Ensure required date + all output fields exist
card_json.setdefault("date", date_str)
card_json.setdefault("dayLabel", day_label)
card_json.setdefault("dateLabel", date_label)
for f in OUTPUT_FIELDS:
    card_json.setdefault(f, [])

# --- URL validation: HEAD-check all URLs in parallel, drop dead ones ---
print("Step 3: HEAD-checking URLs...")
all_urls = []
for f in OUTPUT_FIELDS:
    all_urls += [x.get("url","") for x in card_json.get(f, [])]
live_map = batch_check_urls(all_urls)
live_count = sum(1 for v in live_map.values() if v)
print(f"  {live_count}/{len(live_map)} URLs are live")

for f in OUTPUT_FIELDS:
    if f in REPO_FIELDS:
        card_json[f] = validate_repo_items(card_json.get(f, []), live_map)
    else:
        card_json[f] = validate_news_items(card_json.get(f, []), live_map)

# --- Dedup by URL against last 3 days ---
if recent_urls:
    removed_total = 0
    for f in OUTPUT_FIELDS:
        before = len(card_json.get(f, []))
        card_json[f] = [x for x in card_json.get(f, []) if not x.get("url") or x["url"] not in recent_urls]
        removed_total += before - len(card_json[f])
    if removed_total:
        print(f"Dedup removed {removed_total} duplicate item(s) found in last 3 days")

# --- Update cards.json (rolling 30-day window) ---
cards = [c for c in cards if c.get("date") != date_str]
cutoff = now - timedelta(days=30)
cards = [c for c in cards if datetime.strptime(c["date"], "%Y-%m-%d") >= cutoff.replace(tzinfo=None)]
cards.insert(0, card_json)

with open("cards.json", "w", encoding="utf-8") as f:
    json.dump(cards, f, ensure_ascii=False, indent=2)

summary = " ".join(f"{fld}:{len(card_json.get(fld,[]))}" for fld in OUTPUT_FIELDS)
print(f"Done! {len(cards)} cards | {summary}")
