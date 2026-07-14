#!/usr/bin/env python3
"""Monthly digest generator — aggregate-only, NO Gemini/LLM by design (decision:
monthly stays deterministic aggregation over already-validated daily data, unlike
daily/weekly which call Gemini — lower fake-news risk, no extra API cost).

Two modes:
  --backfill YYYY-MM   Build monthly from cards.json items in that month with real
                       URLs. Dedupes by URL. Safe — no fake-news risk because items
                       are copies of validated daily data.
  default              Roll up PREVIOUS month at start of new month: same aggregate
                       logic over cards.json (no LLM summarisation in either mode).

TOP RULE: every news item MUST have a real, HEAD-validated URL.
"""
import json, argparse
from datetime import datetime, timedelta
from digest_utils import batch_check_urls, GITHUB_REPO_RE, list_item_fields
from jina_fetch import github_search
from time_utils import now_vn
from monthly_ranking import dedupe_by_url, rank_news, rank_repos

MAX_MONTHS = 12  # rolling window
MONTHS_VI  = ["", "Tháng 1","Tháng 2","Tháng 3","Tháng 4","Tháng 5","Tháng 6",
              "Tháng 7","Tháng 8","Tháng 9","Tháng 10","Tháng 11","Tháng 12"]


def month_label(year: int, month: int) -> str:
    return f"{MONTHS_VI[month]}/{year}"


def month_bounds(year: int, month: int) -> tuple[str, str]:
    first = datetime(year, month, 1).date()
    last  = (datetime(year+1, 1, 1) - timedelta(days=1)).date() if month == 12 \
            else (datetime(year, month+1, 1) - timedelta(days=1)).date()
    return first.isoformat(), last.isoformat()


def filter_items_in_month(cards: list, year: int, month: int) -> tuple[list, list, list]:
    """Pull all items from cards in target month, topic-agnostic.
    Splits into (news, repos, gaming) heuristically:
      - has github.com URL → repos
      - field name contains 'gaming' → gaming
      - else → news
    All items include a _date + _field marker for downstream ranking."""
    news, repos, gaming = [], [], []
    for c in cards:
        try:
            d = datetime.strptime(c["date"], "%Y-%m-%d").date()
        except (ValueError, KeyError):
            continue
        if d.year != year or d.month != month:
            continue
        for field in list_item_fields(c):
            for x in c.get(field, []):
                if not isinstance(x, dict) or not x.get("url"):
                    continue
                item = {**x, "_date": c["date"], "_field": field}
                url = x["url"]
                if url.startswith("https://github.com/") and x.get("name"):
                    repos.append(item)
                elif "gaming" in field.lower():
                    gaming.append(item)
                else:
                    news.append(item)
    return news, repos, gaming


def fetch_live_github_for_month(year: int, month: int) -> list:
    """Live GitHub Search for repos created/pushed in target month — fallback for sparse cards."""
    first, _ = month_bounds(year, month)
    queries = [
        f"claude OR anthropic OR mcp pushed:>{first} stars:>50",
        f"agent OR \"ai tools\" pushed:>{first} stars:>200",
        f"llm OR ai pushed:>{first} stars:>500",
    ]
    seen = {}
    for q in queries:
        for r in github_search(q, max_results=8):
            if r["url"] and r["url"] not in seen:
                seen[r["url"]] = {
                    "name":   r["name"],
                    "url":    r["url"],
                    "desc":   r["desc"][:200],
                    "stars":  r["stars"],
                    "verdict":"yes",
                    "reason": f"Trending {month_label(year, month)}",
                }
    return list(seen.values())


def build_monthly(year: int, month: int, cards: list, fetch_live: bool = False) -> dict | None:
    news, repos, gaming = filter_items_in_month(cards, year, month)
    news   = dedupe_by_url(news)
    repos  = dedupe_by_url(repos)
    gaming = dedupe_by_url(gaming)

    # Fallback: if repos sparse for this month (e.g. current month early), pull live GitHub
    if fetch_live and len(repos) < 4:
        print(f"  Sparse repos ({len(repos)}) — fetching live GitHub for {month_label(year, month)}...")
        live = fetch_live_github_for_month(year, month)
        existing_urls = {r["url"] for r in repos}
        for r in live:
            if r["url"] not in existing_urls:
                repos.append(r)

    # HEAD re-check to catch any URL that died since last scrub
    all_urls = [x["url"] for x in news + repos + gaming if x.get("url")]
    if all_urls:
        live = batch_check_urls(all_urls)
        news   = [n for n in news   if live.get(n["url"], False)]
        repos  = [r for r in repos  if live.get(r["url"], False) and GITHUB_REPO_RE.match(r["url"])]
        gaming = [g for g in gaming if live.get(g["url"], False)]

    if not news and not repos and not gaming:
        print(f"  No live items found for {month_label(year, month)}")
        return None

    from_date, to_date = month_bounds(year, month)
    return {
        "monthLabel": month_label(year, month),
        "fromDate":   from_date,
        "toDate":     to_date,
        "topNews":    rank_news(news,   top_n=10),
        "topRepos":   rank_repos(repos, top_n=8),
        "topGaming":  rank_news(gaming, top_n=5),
    }


def upsert_monthly(monthly_card: dict, path: str = "monthly.json") -> None:
    try:
        with open(path, "r", encoding="utf-8") as f:
            months = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        months = []
    months = [m for m in months if m.get("monthLabel") != monthly_card["monthLabel"]]
    months.insert(0, monthly_card)

    # Sort desc by fromDate, keep last MAX_MONTHS
    months.sort(key=lambda m: m.get("fromDate", ""), reverse=True)
    months = months[:MAX_MONTHS]

    with open(path, "w", encoding="utf-8") as f:
        json.dump(months, f, ensure_ascii=False, indent=2)
    print(f"  Wrote {path} ({len(months)} months)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backfill", help="Backfill specific month (YYYY-MM)")
    args = ap.parse_args()

    with open("cards.json", "r", encoding="utf-8") as f:
        cards = json.load(f)

    now = now_vn()

    if args.backfill:
        year, month = map(int, args.backfill.split("-"))
        # Fetch live GitHub if backfilling current month (sparse cards expected)
        is_current = (year == now.year and month == now.month)
        print(f"Backfilling {month_label(year, month)} from cards.json{' + live GitHub' if is_current else ''}...")
        m = build_monthly(year, month, cards, fetch_live=is_current)
        if m:
            print(f"  topNews:{len(m['topNews'])} topRepos:{len(m['topRepos'])} topGaming:{len(m['topGaming'])}")
            upsert_monthly(m)
        return

    # Default: roll up PREVIOUS month
    if now.month == 1:
        year, month = now.year - 1, 12
    else:
        year, month = now.year, now.month - 1
    print(f"Rolling up previous month: {month_label(year, month)}")
    m = build_monthly(year, month, cards, fetch_live=False)
    if m:
        upsert_monthly(m)


if __name__ == "__main__":
    main()
