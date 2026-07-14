#!/usr/bin/env python3
"""Weekly digest generator — runs every Sunday, summarises last 7 daily cards via Gemini.
TOP RULE: every news/gaming item MUST have a real, HEAD-validated URL — no exceptions.
CI (morning.yml) calls this file directly — keep entry name."""
import json
from datetime import datetime, timedelta

from digest_utils import batch_check_urls, GITHUB_REPO_RE, list_item_fields
from gemini_client import call_gemini
from json_extract import parse_llm_json
from time_utils import now_vn

MIN_CARDS  = 3   # skip generation if fewer cards available
MAX_WEEKS  = 12  # rolling window for weekly.json


def load_week_cards(now: datetime, path: str = "cards.json") -> list:
    """Cards from last 7 days. M6 guard: skip cards with missing/malformed date."""
    with open(path, "r", encoding="utf-8") as f:
        all_cards = json.load(f)
    cutoff = now - timedelta(days=7)
    week_cards = []
    for c in all_cards:
        d = c.get("date")
        if not d:
            continue
        try:
            card_date = datetime.strptime(d, "%Y-%m-%d")
        except ValueError:
            continue
        if card_date >= cutoff.replace(tzinfo=None):
            week_cards.append(c)
    return week_cards


def compact_cards(cards: list) -> str:
    """Build context topic-agnostically — every list field with URL becomes a row."""
    rows = []
    for c in cards:
        date = c.get("date", "")
        for field in list_item_fields(c):
            for x in c.get(field, []):
                if not isinstance(x, dict):
                    continue
                url = (x.get("url") or "").strip()
                if not url:
                    continue
                # Repo item has name + stars, news has title
                if x.get("name"):
                    rows.append(f"[{date}][{field}] {x['name']} | URL: {url} | ⭐{x.get('stars','')} | {x.get('desc','')[:120]}")
                else:
                    rows.append(f"[{date}][{field}][{x.get('tag','')}] {x.get('title','')} | URL: {url} | {x.get('desc','')[:120]}")
    return "\n".join(rows)


def build_weekly_prompt(context: str, week_label: str, from_date: str, to_date: str) -> str:
    return f"""Dưới đây là dữ liệu Morning Digest từ {from_date} đến {to_date} (chỉ items có URL thật):

{context}

Tổng hợp Weekly Digest cho {week_label}. Trả về CHỈ JSON (không markdown, không text thêm):
{{
  "weekLabel": "{week_label}",
  "fromDate": "{from_date}",
  "toDate": "{to_date}",
  "highlights": [
    {{"title":"emoji+tên","desc":"tóm tắt tiếng Việt 2-3 câu nêu impact","tag":"hot|api|feature|deprecate|model","tagLabel":"🔥 HOT|🔧 API|✨ FEATURE|⏰ DEADLINE|🧠 MODEL","url":"https://...nguyên-xi-từ-context"}}
  ],
  "topRepos": [
    {{"name":"owner/repo","url":"https://github.com/owner/repo","desc":"lý do nổi bật tuần này tiếng Việt","stars":"12K+","verdict":"yes"}}
  ],
  "topGaming": [
    {{"title":"emoji+tên","desc":"tóm tắt tiếng Việt","tag":"chart|monet|gameplay|social-casino|casual","tagLabel":"📊 CHART|💰 MONET|🎮 GAMEPLAY|🎰 SOCIAL|🎈 CASUAL","url":"https://...nguyên-xi-từ-context"}}
  ]
}}

HARD RULES (TOP PRIORITY — KHÔNG VI PHẠM):
1. MỌI item BẮT BUỘC có field "url" với URL THẬT, copy NGUYÊN XI từ "URL:" trong context trên. KHÔNG bịa, KHÔNG sửa, KHÔNG đoán.
2. Item nào không có URL trong context → BỎ QUA, không đưa vào output.
3. Repo: name + url + stars phải khớp NGUYÊN VĂN context.
4. highlights: 3-5 items quan trọng nhất tuần. topRepos: 3 items verdict=yes nổi bật nhất. topGaming: 2-3 items nếu có data gaming.
5. Thà ít mà thật, đừng cố nhồi đủ số lượng. Tiếng Việt ngắn gọn."""


def strict_filter(items: list, live_map: dict, require_github: bool = False) -> list:
    """Drop any item whose URL is missing/dead. For repos, also require github.com/owner/repo format."""
    cleaned = []
    for it in items:
        url = (it.get("url") or "").strip()
        if not url:
            print(f"  [strict] dropped (no URL): {it.get('title') or it.get('name')}")
            continue
        if require_github and not GITHUB_REPO_RE.match(url):
            print(f"  [strict] dropped (bad repo format): {url}")
            continue
        if not live_map.get(url, False):
            print(f"  [strict] dropped (dead URL): {url}")
            continue
        cleaned.append(it)
    return cleaned


def validate_weekly_card(weekly_card: dict) -> dict:
    """STRICT validation: every news/gaming item must have live URL; repos must match github.com format + live."""
    print("Validating URLs (HEAD-check)...")
    all_urls = (
        [it.get("url", "") for it in weekly_card.get("highlights", [])] +
        [it.get("url", "") for it in weekly_card.get("topRepos", [])] +
        [it.get("url", "") for it in weekly_card.get("topGaming", [])]
    )
    live_map = batch_check_urls(all_urls)
    print(f"  {sum(live_map.values())}/{len(live_map)} URLs are live")

    weekly_card["highlights"] = strict_filter(weekly_card.get("highlights", []), live_map)
    weekly_card["topRepos"]   = strict_filter(weekly_card.get("topRepos", []),   live_map, require_github=True)
    weekly_card["topGaming"]  = strict_filter(weekly_card.get("topGaming", []),  live_map)
    return weekly_card


def update_weekly_file(weekly_card: dict, week_label: str, path: str = "weekly.json") -> list:
    """Rolling MAX_WEEKS window; replace this week's entry if already present."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            weeklies = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        weeklies = []

    weeklies = [w for w in weeklies if w.get("weekLabel") != week_label]
    weeklies.insert(0, weekly_card)
    weeklies = weeklies[:MAX_WEEKS]

    with open(path, "w", encoding="utf-8") as f:
        json.dump(weeklies, f, ensure_ascii=False, indent=2)
    return weeklies


def main():
    now = now_vn()
    week_cards = load_week_cards(now)

    if len(week_cards) < MIN_CARDS:
        print(f"Only {len(week_cards)} cards this week (min {MIN_CARDS}) — skipping weekly digest")
        raise SystemExit(0)

    from_date  = week_cards[-1]["date"]
    to_date    = week_cards[0]["date"]
    week_num   = now.isocalendar()[1]
    week_label = f"Tuần {week_num}/{now.year}"

    context = compact_cards(week_cards)
    if not context.strip():
        print("No items with URLs in week — skipping weekly digest")
        raise SystemExit(0)

    prompt = build_weekly_prompt(context, week_label, from_date, to_date)
    print(f"Generating weekly digest: {week_label} ({from_date} → {to_date}) from {len(week_cards)} cards...")

    text, _ = call_gemini(prompt, use_search=False, thinking_budget=0, max_output_tokens=2048)
    if not text:
        print("All attempts failed — skipping weekly digest")
        raise SystemExit(1)

    weekly_card = parse_llm_json(text)
    if not weekly_card:
        print("Could not parse weekly JSON — skipping")
        raise SystemExit(1)

    weekly_card = validate_weekly_card(weekly_card)
    weeklies = update_weekly_file(weekly_card, week_label)

    print(f"Done! {len(weeklies)} weekly digests | "
          f"highlights:{len(weekly_card.get('highlights',[]))} "
          f"repos:{len(weekly_card.get('topRepos',[]))} "
          f"gaming:{len(weekly_card.get('topGaming',[]))}")


if __name__ == "__main__":
    main()
