#!/usr/bin/env python3
"""Daily morning digest generator — orchestrator: load config → fetch context →
build prompt → call Gemini (fallback Google Search) → parse → validate → dedup →
write cards.json. CI (morning.yml) calls this file directly — keep entry name."""
import json
from datetime import datetime, timedelta

from digest_utils import (
    get_recent_titles, get_recent_urls, batch_check_urls,
    validate_news_items, validate_repo_items,
    build_dedup_index, is_duplicate_title, DEDUP_DAYS,
)
from jina_fetch import fetch_topic_context
from gemini_client import call_gemini
from json_extract import parse_llm_json
from prompt_builder import build_daily_prompt
from time_utils import now_vn

DAY_NAMES = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]


def load_config(path: str = "config.json") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_cards(path: str = "cards.json") -> list:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def fetch_contexts(topics: dict, month_year: str) -> tuple[dict, set[str]]:
    """Fetch pre-search web context per topic. Returns (topic_contexts, trusted_urls).
    trusted_urls = union of REAL URLs from RSS/Jina/GitHub fetch layer across all
    topics — passed downstream to validate_card so known-real URLs skip the
    HEAD-check (some sites like vnexpress.net block bot HEAD/GET and would otherwise
    be false-negative "dropped as dead")."""
    topic_contexts = {}
    trusted_urls: set[str] = set()
    for key, topic in topics.items():
        ctx, urls = fetch_topic_context(topic, month_year)
        topic_contexts[key] = ctx
        trusted_urls |= urls
    return topic_contexts, trusted_urls


def empty_card(date_str: str, day_label: str, date_label: str, output_fields: list) -> dict:
    c = {"date": date_str, "dayLabel": day_label, "dateLabel": date_label}
    for f in output_fields:
        c[f] = []
    return c


def generate_card_json(prompt: str, has_data: bool, date_str: str, day_label: str,
                        date_label: str, output_fields: list) -> dict:
    """Call Gemini (pre-fetched context first, fallback Google Search grounding), parse JSON."""
    text, _ = call_gemini(prompt, use_search=False)
    if not text or not has_data:
        print("Falling back to Gemini + Google Search grounding...")
        text2, _ = call_gemini(prompt, retries=1, use_search=True)
        if text2:
            text = text2

    if not text:
        print("All attempts failed. Using fallback card.")
        return empty_card(date_str, day_label, date_label, output_fields)

    print(f"Raw response preview: {text[:300]}...")
    card_json = parse_llm_json(text)
    if not card_json:
        print("Could not parse JSON, using fallback")
        card_json = empty_card(date_str, day_label, date_label, output_fields)

    card_json.setdefault("date", date_str)
    card_json.setdefault("dayLabel", day_label)
    card_json.setdefault("dateLabel", date_label)
    for f in output_fields:
        card_json.setdefault(f, [])
    return card_json


def validate_card(card_json: dict, output_fields: list, repo_fields: list,
                   trusted_urls: set) -> dict:
    """HEAD-check URLs in parallel, drop dead/invalid items. URLs already known real
    (trusted_urls, sourced directly from RSS/Jina/GitHub fetch layer) skip HEAD-check
    entirely — avoids false-negative drops + saves requests."""
    print("Step 3: HEAD-checking URLs...")
    all_urls = []
    for f in output_fields:
        all_urls += [x.get("url", "") for x in card_json.get(f, [])]
    untrusted_urls = [u for u in all_urls if u and u not in trusted_urls]
    live_map = batch_check_urls(untrusted_urls)
    live_count = sum(1 for v in live_map.values() if v)
    print(f"  {live_count}/{len(live_map)} untrusted URLs are live "
          f"({len(trusted_urls)} trusted URLs skip-checked)")

    for f in output_fields:
        if f in repo_fields:
            card_json[f] = validate_repo_items(card_json.get(f, []), live_map)
        else:
            card_json[f] = validate_news_items(card_json.get(f, []), live_map, trusted_urls)
    return card_json


def dedup_card(card_json: dict, output_fields: list, recent_urls: set,
                recent_norms: set, recent_tokens: list) -> dict:
    """Drop items duplicate vs last DEDUP_DAYS: by URL exact + normalized/token-overlap title."""
    removed_url = removed_title = 0
    for f in output_fields:
        kept = []
        for x in card_json.get(f, []):
            url = (x.get("url") or "").strip()
            if url and url in recent_urls:
                removed_url += 1
                print(f"  [dedup:url]   drop {f}: {x.get('title') or x.get('name','')[:60]}")
                continue
            title = x.get("title") or x.get("name") or ""
            if is_duplicate_title(title, recent_norms, recent_tokens):
                removed_title += 1
                print(f"  [dedup:title] drop {f}: {title[:60]}")
                continue
            kept.append(x)
        card_json[f] = kept
    if removed_url or removed_title:
        print(f"Dedup: dropped {removed_url} by URL + {removed_title} by title (window {DEDUP_DAYS} days)")
    return card_json


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

    with open(path, "w", encoding="utf-8") as f:
        json.dump(kept, f, ensure_ascii=False, indent=2)
    return kept


def main():
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


if __name__ == "__main__":
    main()
