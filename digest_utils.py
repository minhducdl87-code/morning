"""Shared utilities for Morning Digest generators — thin facade re-exporting
dedup_utils (title/URL dedup, topic-agnostic field helpers) and url_check
(HEAD-check liveness + item validation). Kept as a single stable import point so
generate_card.py / generate_weekly.py / generate_monthly.py / scrub_cards.py /
notify-telegram.py don't need to change their `from digest_utils import ...`."""
from dedup_utils import (
    DEDUP_DAYS, list_item_fields, normalize_title,
    build_dedup_index, is_duplicate_title,
    get_recent_titles, get_recent_urls,
)
from url_check import (
    GITHUB_REPO_RE, HTTP_TIMEOUT, HEAD_WORKERS, URL_BLACKLIST,
    is_url_live, batch_check_urls,
    validate_news_items, validate_repo_items,
)

__all__ = [
    "DEDUP_DAYS", "list_item_fields", "normalize_title",
    "build_dedup_index", "is_duplicate_title",
    "get_recent_titles", "get_recent_urls",
    "GITHUB_REPO_RE", "HTTP_TIMEOUT", "HEAD_WORKERS", "URL_BLACKLIST",
    "is_url_live", "batch_check_urls",
    "validate_news_items", "validate_repo_items",
]
