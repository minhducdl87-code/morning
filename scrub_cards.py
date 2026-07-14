#!/usr/bin/env python3
"""Topic-agnostic scrub: HEAD-check all URLs in cards.json + weekly.json + monthly.json.
Strict-drop dead/no-URL news items. Strict-drop bad-format/dead repo items.
Works with any topic set (old + new pivot fields alike)."""
import json
from digest_utils import (
    batch_check_urls, validate_news_items, validate_repo_items,
    GITHUB_REPO_RE, list_item_fields,
)


def _is_repo_field(items: list) -> bool:
    """Heuristic: field contains github.com/owner/repo URLs → treat as repo field."""
    if not items:
        return False
    sample = items[0]
    if not isinstance(sample, dict):
        return False
    url = (sample.get("url") or "").strip()
    return bool(GITHUB_REPO_RE.match(url))


def scrub_file(path: str) -> None:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"{path}: not found, skip")
        return

    items = data if isinstance(data, list) else [data]

    # Collect all URLs across all fields of all entries
    all_urls = []
    for entry in items:
        for f in list_item_fields(entry):
            for x in entry[f] or []:
                if isinstance(x, dict) and x.get("url"):
                    all_urls.append(x["url"])

    print(f"\nChecking {len(set(all_urls))} unique URLs in {path}...")
    live_map = batch_check_urls(all_urls) if all_urls else {}

    for entry in items:
        for f in list_item_fields(entry):
            arr = entry[f] or []
            if not arr or not isinstance(arr[0], dict):
                continue
            if _is_repo_field(arr):
                entry[f] = validate_repo_items(arr, live_map)
            else:
                entry[f] = validate_news_items(arr, live_map)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Wrote {path}")


if __name__ == "__main__":
    scrub_file("cards.json")
    scrub_file("weekly.json")
    scrub_file("monthly.json")
