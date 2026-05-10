#!/usr/bin/env python3
"""One-time scrub: HEAD-check all URLs in cards.json + weekly.json.
Clear dead news URLs, drop dead repo items. Removes accumulated fake data
from before the URL-validation fix."""
import json
from digest_utils import batch_check_urls, validate_news_items, validate_repo_items


def scrub_cards(path: str = "cards.json") -> None:
    with open(path, "r", encoding="utf-8") as f:
        cards = json.load(f)

    # Collect all URLs across all cards for one batched check
    all_urls = []
    for c in cards:
        all_urls += [n.get("url","") for n in c.get("news", [])]
        all_urls += [g.get("url","") for g in c.get("gamingNews", [])]
        all_urls += [r.get("url","") for r in c.get("repos", [])]

    print(f"Checking {len(set(u for u in all_urls if u))} unique URLs across {len(cards)} cards...")
    live_map = batch_check_urls(all_urls)
    live_count = sum(1 for v in live_map.values() if v)
    print(f"  {live_count}/{len(live_map)} live\n")

    for c in cards:
        before_news  = len(c.get("news", []))
        before_gam   = len(c.get("gamingNews", []))
        before_repos = len(c.get("repos", []))

        c["news"]       = validate_news_items(c.get("news", []),       live_map)
        c["gamingNews"] = validate_news_items(c.get("gamingNews", []), live_map)
        c["repos"]      = validate_repo_items(c.get("repos", []),      live_map)

        repo_dropped = before_repos - len(c["repos"])
        cleared = sum(1 for n in c["news"] if not n.get("url")) + sum(1 for g in c["gamingNews"] if not g.get("url"))
        print(f"  {c['date']}: news/gaming kept {before_news}+{before_gam}, URLs cleared in {cleared}; repos {before_repos}→{len(c['repos'])} (dropped {repo_dropped})")

    with open(path, "w", encoding="utf-8") as f:
        json.dump(cards, f, ensure_ascii=False, indent=2)
    print(f"\nWrote {path}")


def scrub_weekly(path: str = "weekly.json") -> None:
    """Best-effort scrub for weekly digest if it has same URL fields."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return

    # weekly.json structure may differ — only scrub if it has same fields
    items = data if isinstance(data, list) else [data]
    all_urls = []
    for it in items:
        for k in ("news", "gamingNews", "repos", "topNews", "topRepos", "highlights", "topGaming"):
            for x in it.get(k, []) or []:
                u = x.get("url", "")
                if u:
                    all_urls.append(u)

    print(f"\nChecking {len(set(all_urls))} URLs in {path}...")
    live_map = batch_check_urls(all_urls) if all_urls else {}
    for it in items:
        # News-like fields: strict drop if no live URL (top rule)
        for k in ("news", "gamingNews", "topNews", "highlights", "topGaming"):
            if k in it:
                it[k] = validate_news_items(it.get(k, []) or [], live_map)
        # Repo fields: drop bad-format + dead
        for k in ("repos", "topRepos"):
            if k in it:
                it[k] = validate_repo_items(it.get(k, []) or [], live_map)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Wrote {path}")


if __name__ == "__main__":
    scrub_cards("cards.json")
    scrub_weekly("weekly.json")
