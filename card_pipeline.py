"""Shared card-generation pipeline steps used by BOTH the morning flow
(generate_card.py) and the evening flow (evening_update.py): fetch web
context, call Gemini + parse, HEAD-check/validate URLs, dedup vs recent
window, write cards.json. Split out so evening_update.py doesn't need to
import the __main__ script module — see H1-style convention."""
import json

from digest_utils import (
    batch_check_urls, validate_news_items, validate_repo_items,
    is_duplicate_title, DEDUP_DAYS,
)
from jina_fetch import fetch_topic_context
from gemini_client import call_gemini
from json_extract import parse_llm_json


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


def _count_items(card: dict | None, output_fields: list) -> int:
    if not card:
        return 0
    return sum(len(card.get(f, []) or []) for f in output_fields)


def generate_card_json(prompt: str, has_data: bool, date_str: str, day_label: str,
                        date_label: str, output_fields: list) -> dict:
    """Call Gemini (pre-fetched context), parse JSON. Retry with Google Search
    grounding when the response is missing/unparseable/empty (0 items) — a
    truncated or malformed JSON must NOT silently produce an empty digest."""
    text, _ = call_gemini(prompt, use_search=False)
    if text:
        print(f"Raw response preview: {text[:300]}...")
    card_json = parse_llm_json(text) if text else None
    total = _count_items(card_json, output_fields)

    # Fallback when nothing usable came back (empty text, parse failure, or 0 items).
    if total == 0 or not has_data:
        print(f"Primary attempt yielded {total} items — falling back to Gemini + Google Search grounding...")
        text2, _ = call_gemini(prompt, retries=1, use_search=True)
        card2 = parse_llm_json(text2) if text2 else None
        if _count_items(card2, output_fields) > 0:
            card_json = card2

    if not card_json:
        print("All attempts failed / unparseable. Using empty card.")
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


def write_cards_file(cards: list, path: str = "cards.json") -> None:
    """Write the full cards list as-is (no filtering/reordering) — used by the
    evening flow which mutates cards[0] in place instead of inserting a new card."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cards, f, ensure_ascii=False, indent=2)
