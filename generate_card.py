#!/usr/bin/env python3
"""Daily morning digest generator — orchestrator: load config → fetch context →
build prompt → call Gemini (fallback Google Search) → parse → validate → dedup →
write cards.json. CI (morning.yml) calls this file directly — keep entry name.

RUN_MODE env var ("morning"|"evening", default "morning") selects the flow:
  - morning: original behavior — new card for today (this file, main_morning()).
  - evening: appends fresh items to today's existing card (22h VN update).
    Implemented in evening_update.py; shared pipeline steps (fetch/Gemini/
    validate/dedup/write) live in card_pipeline.py so both flows reuse them."""
import json
import os
from datetime import datetime, timedelta

from digest_utils import get_recent_titles, get_recent_urls, build_dedup_index, DEDUP_DAYS
from card_pipeline import fetch_contexts, generate_card_json, validate_card, dedup_card, write_cards_file
from prompt_builder import build_daily_prompt
from time_utils import now_vn

DAY_NAMES = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]
RUN_MODE = os.environ.get("RUN_MODE", "morning")


def load_config(path: str = "config.json") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_cards(path: str = "cards.json") -> list:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def update_cards_file(cards: list, card_json: dict, date_str: str, now: datetime,
                       path: str = "cards.json") -> list:
    """Rolling 30-day window; replace today's entry if already present.
    M6 guard: skip cards with missing/malformed date instead of crashing."""
    cards = [c for c in cards if c.get("date") != date_str]
    cutoff = now - timedelta(days=30)
    kept = []
    for c in cards:
        d = c.get("date")
        if not d:
            continue
        try:
            card_date = datetime.strptime(d, "%Y-%m-%d")
        except ValueError:
            continue
        if card_date >= cutoff.replace(tzinfo=None):
            kept.append(c)
    kept.insert(0, card_json)
    write_cards_file(kept, path)
    return kept


def main_morning():
    config = load_config()
    topics = {k: v for k, v in config["topics"].items() if v.get("enabled", True)}
    cards = load_cards()

    now = now_vn()
    date_str   = now.strftime("%Y-%m-%d")
    date_label = now.strftime("%d/%m/%Y")
    day_label  = DAY_NAMES[now.weekday()]
    month_year = now.strftime("%B %Y")

    recent_titles = get_recent_titles(cards, date_str, now, days=DEDUP_DAYS)
    recent_urls   = get_recent_urls(cards, date_str, now, days=DEDUP_DAYS)
    recent_norms, recent_tokens = build_dedup_index(recent_titles)
    print(f"Dedup window: {DEDUP_DAYS} days | {len(recent_titles)} recent titles, {len(recent_urls)} recent URLs")

    print(f"Generating card for {date_str} | topics: {list(topics.keys())}...")
    print("Step 1: Fetching web content...")
    topic_contexts, trusted_urls = fetch_contexts(topics, month_year)
    has_data = bool(trusted_urls)
    print(f"Fetch done. has_data={has_data} trusted_urls={len(trusted_urls)}")

    output_fields = [t["output_field"] for t in topics.values() if t.get("output_field")]
    repo_fields   = [t["output_field"] for t in topics.values() if t.get("data_source") == "github_api"]

    prompt = build_daily_prompt(
        topics, recent_titles, topic_contexts,
        day_label, date_label, date_str, DEDUP_DAYS,
        tone_guidance=config.get("tone_guidance", ""),
    )
    print(f"Step 2: Calling Gemini... (prompt: {len(prompt)} chars)")

    card_json = generate_card_json(prompt, has_data, date_str, day_label, date_label, output_fields)
    card_json = validate_card(card_json, output_fields, repo_fields, trusted_urls)
    card_json = dedup_card(card_json, output_fields, recent_urls, recent_norms, recent_tokens)

    cards = update_cards_file(cards, card_json, date_str, now)

    summary = " ".join(f"{fld}:{len(card_json.get(fld,[]))}" for fld in output_fields)
    print(f"Done! {len(cards)} cards | {summary}")


def main():
    if RUN_MODE == "evening":
        from evening_update import run_evening
        config = load_config()
        topics = {k: v for k, v in config["topics"].items() if v.get("enabled", True)}
        cards = load_cards()
        run_evening(config, topics, cards, now_vn())
    else:
        main_morning()


if __name__ == "__main__":
    main()
