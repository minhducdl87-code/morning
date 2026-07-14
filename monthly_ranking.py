"""Pure ranking/dedup functions for the monthly digest — split out of
generate_monthly.py to stay under the 200-LOC file guideline and keep these
testable in isolation (no I/O, no network)."""
from collections import OrderedDict


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
    items = sorted(items, key=lambda x: (priority.get(x.get("tag", ""), 9), x.get("_date", "")), reverse=False)
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
            if "K" in s:
                return float(s.replace("K", "")) * 1000
            return float(s)
        except ValueError:
            return 0

    verdict_rank = {"yes": 0, "maybe": 1, "skip": 2}
    items = sorted(items, key=lambda x: (verdict_rank.get(x.get("verdict", "skip"), 3), -stars_num(x.get("stars", ""))))
    out = []
    for it in items[:top_n]:
        clean = {k: v for k, v in it.items() if not k.startswith("_")}
        out.append(clean)
    return out
