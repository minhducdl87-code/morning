"""Evening update flow (22h VN, RUN_MODE=evening) — appends fresh items to
TODAY's existing morning card instead of creating a new one. Split out of
generate_card.py to keep that file thin (see H1-style convention).

Guards (both no-op, exit 0 via caller):
  - No morning card for today yet (cron ran before morning job, or sang ngày
    mới trước khi morning job kịp chạy) → skip.
  - cards[0]["eveningDone"] already True → skip (idempotent, safe to re-run
    if GitHub Actions retries or Cloudflare cron fires twice)."""
from digest_utils import get_recent_titles, get_recent_urls, build_dedup_index, DEDUP_DAYS
from prompt_builder import build_daily_prompt
from card_pipeline import fetch_contexts, generate_card_json, validate_card, dedup_card, write_cards_file
from generate_card import DAY_NAMES


def run_evening(config: dict, topics: dict, cards: list, now) -> bool:
    """Fetch fresh context, dedup vs (7-day window + today's morning items),
    append survivors to cards[0] tagged addedEvening=True. Returns True if an
    update was performed, False if skipped (guard hit)."""
    date_str = now.strftime("%Y-%m-%d")

    if not cards or cards[0].get("date") != date_str:
        print("No morning card for today yet — skip evening update")
        return False
    if cards[0].get("eveningDone"):
        print("Evening update already done for today — skip")
        return False

    morning_card = cards[0]
    date_label = now.strftime("%d/%m/%Y")
    day_label  = DAY_NAMES[now.weekday()]
    month_year = now.strftime("%B %Y")

    output_fields = [t["output_field"] for t in topics.values() if t.get("output_field")]
    repo_fields   = [t["output_field"] for t in topics.values() if t.get("data_source") == "github_api"]

    # Dedup context: last DEDUP_DAYS days (excluding today, as usual) PLUS today's
    # own morning items — unlike the morning run, evening must include today so it
    # only keeps items with a genuinely new angle vs what was already published.
    recent_titles = get_recent_titles(cards, date_str, now, days=DEDUP_DAYS)
    recent_urls   = get_recent_urls(cards, date_str, now, days=DEDUP_DAYS)
    for f in output_fields:
        for x in morning_card.get(f, []):
            if not isinstance(x, dict):
                continue
            if x.get("title"):
                recent_titles.append(x["title"])
            if x.get("url"):
                recent_urls.add(x["url"])
    recent_norms, recent_tokens = build_dedup_index(recent_titles)
    print(f"Evening dedup: {DEDUP_DAYS}d window + today's morning card | "
          f"{len(recent_titles)} titles, {len(recent_urls)} urls")

    print(f"Generating evening update for {date_str} | topics: {list(topics.keys())}...")
    topic_contexts, trusted_urls = fetch_contexts(topics, month_year)
    has_data = bool(trusted_urls)
    print(f"Fetch done. has_data={has_data} trusted_urls={len(trusted_urls)}")

    prompt = build_daily_prompt(
        topics, recent_titles, topic_contexts,
        day_label, date_label, date_str, DEDUP_DAYS,
        tone_guidance=config.get("tone_guidance", ""),
    )

    card_json = generate_card_json(prompt, has_data, date_str, day_label, date_label, output_fields)
    card_json = validate_card(card_json, output_fields, repo_fields, trusted_urls)
    card_json = dedup_card(card_json, output_fields, recent_urls, recent_norms, recent_tokens)

    added = 0
    for f in output_fields:
        new_items = [x for x in card_json.get(f, []) if isinstance(x, dict)]
        for x in new_items:
            x["addedEvening"] = True
        if new_items:
            morning_card.setdefault(f, [])
            morning_card[f].extend(new_items)
            added += len(new_items)

    morning_card["eveningDone"] = True
    write_cards_file(cards)
    print(f"Evening update done! {added} new items merged into {date_str}")
    return True
