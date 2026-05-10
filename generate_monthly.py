#!/usr/bin/env python3
"""Monthly digest generator.

Two modes:
  --backfill YYYY-MM   Aggregate-only (no LLM): build monthly from cards.json items
                       in that month with real URLs. Dedupes by URL. Safe — no
                       fake-news risk because items are copies of validated daily data.
  default              Roll up PREVIOUS month at start of new month: read weekly.json
                       entries that fall in prev month, summarise via Gemini if key
                       available, otherwise aggregate-only fallback.

TOP RULE: every news item MUST have a real, HEAD-validated URL.
"""
import json, os, sys, argparse
from collections import OrderedDict
from datetime import datetime, timedelta
from digest_utils import batch_check_urls, GITHUB_REPO_RE

try:
    import zoneinfo
    tz = zoneinfo.ZoneInfo("Asia/Ho_Chi_Minh")
except ImportError:
    from datetime import timezone
    tz = timezone.utc

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
    """Pull all news/repos/gaming items from cards within target month, with URL only."""
    news, repos, gaming = [], [], []
    for c in cards:
        try:
            d = datetime.strptime(c["date"], "%Y-%m-%d").date()
        except (ValueError, KeyError):
            continue
        if d.year != year or d.month != month:
            continue
        for n in c.get("news", []) or []:
            if n.get("url"):
                news.append({**n, "_date": c["date"]})
        for r in c.get("repos", []) or []:
            if r.get("url"):
                repos.append({**r, "_date": c["date"]})
        for g in c.get("gamingNews", []) or []:
            if g.get("url"):
                gaming.append({**g, "_date": c["date"]})
    return news, repos, gaming


def dedupe_by_url(items: list) -> list:
    """Keep first occurrence per URL (chronologically earliest)."""
    seen = OrderedDict()
    for it in items:
        url = it.get("url", "")
        if url and url not in seen:
            seen[url] = it
    return list(seen.values())


def rank_news(items: list, top_n: int = 10) -> list:
    """Rank: prioritise hot/model/deprecate tags, then by recency. Drop _date helper field."""
    priority = {"hot": 0, "model": 1, "deprecate": 2, "feature": 3, "api": 4}
    items = sorted(items, key=lambda x: (priority.get(x.get("tag",""), 9), x.get("_date","")), reverse=False)
    out = []
    for it in items[:top_n]:
        clean = {k: v for k, v in it.items() if not k.startswith("_")}
        out.append(clean)
    return out


def rank_repos(items: list, top_n: int = 8) -> list:
    """Rank repos: verdict=yes first, then by stars (parsed from '12K+' format)."""
    def stars_num(s: str) -> float:
        s = (s or "").rstrip("+").upper()
        try:
            if "K" in s: return float(s.replace("K","")) * 1000
            return float(s)
        except ValueError:
            return 0
    verdict_rank = {"yes": 0, "maybe": 1, "skip": 2}
    items = sorted(items, key=lambda x: (verdict_rank.get(x.get("verdict","skip"), 3), -stars_num(x.get("stars",""))))
    out = []
    for it in items[:top_n]:
        clean = {k: v for k, v in it.items() if not k.startswith("_")}
        out.append(clean)
    return out


def build_monthly(year: int, month: int, cards: list) -> dict | None:
    news, repos, gaming = filter_items_in_month(cards, year, month)
    news   = dedupe_by_url(news)
    repos  = dedupe_by_url(repos)
    gaming = dedupe_by_url(gaming)

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

    if args.backfill:
        year, month = map(int, args.backfill.split("-"))
        print(f"Backfilling {month_label(year, month)} from cards.json...")
        m = build_monthly(year, month, cards)
        if m:
            print(f"  topNews:{len(m['topNews'])} topRepos:{len(m['topRepos'])} topGaming:{len(m['topGaming'])}")
            upsert_monthly(m)
        return

    # Default: roll up PREVIOUS month
    now = datetime.now(tz)
    if now.month == 1:
        year, month = now.year - 1, 12
    else:
        year, month = now.year, now.month - 1
    print(f"Rolling up previous month: {month_label(year, month)}")
    m = build_monthly(year, month, cards)
    if m:
        upsert_monthly(m)


if __name__ == "__main__":
    main()
