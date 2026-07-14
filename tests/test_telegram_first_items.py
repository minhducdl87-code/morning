"""Test notify-telegram first_items function — take N items, dedup by URL."""
import pytest
import os

# Set dummy token to prevent sys.exit() in notify-telegram.py
os.environ["TELEGRAM_BOT_TOKEN"] = "dummy_token"

import sys
import importlib.util

# Import from notify-telegram.py (file with dash in name)
spec = importlib.util.spec_from_file_location(
    "notify_telegram",
    "/".join(__file__.split("\\")[:-2]) + "/notify-telegram.py",
)
notify_telegram = importlib.util.module_from_spec(spec)

# Mock sys.exit to prevent early exit
original_exit = sys.exit
sys.exit = lambda x: None
try:
    spec.loader.exec_module(notify_telegram)
finally:
    sys.exit = original_exit


class TestFirstItems:
    """first_items: take first N items with dedup by URL (config order preserved)."""

    def test_simple_items_no_dedup(self):
        """Simple items, no duplicates."""
        items = [
            ("news", {"title": "News 1", "url": "https://a.com"}),
            ("news", {"title": "News 2", "url": "https://b.com"}),
            ("news", {"title": "News 3", "url": "https://c.com"}),
        ]
        result = notify_telegram.first_items(items, n=3)
        assert len(result) == 3
        assert result[0][1]["url"] == "https://a.com"

    def test_n_limit(self):
        """Only first N items returned."""
        items = [
            ("news", {"title": "News 1", "url": "https://a.com"}),
            ("news", {"title": "News 2", "url": "https://b.com"}),
            ("news", {"title": "News 3", "url": "https://c.com"}),
            ("news", {"title": "News 4", "url": "https://d.com"}),
        ]
        result = notify_telegram.first_items(items, n=2)
        assert len(result) == 2
        assert result[0][1]["url"] == "https://a.com"
        assert result[1][1]["url"] == "https://b.com"

    def test_dedup_by_url(self):
        """Duplicate URLs deduplicated (keep first)."""
        items = [
            ("news", {"title": "News 1", "url": "https://a.com"}),
            ("repos", {"title": "Repo", "url": "https://b.com"}),
            ("news", {"title": "News 1 Again", "url": "https://a.com"}),  # Duplicate URL
            ("news", {"title": "News 3", "url": "https://c.com"}),
        ]
        result = notify_telegram.first_items(items, n=3)
        # Should get a, b, c (skipping the duplicate a)
        assert len(result) == 3
        urls = [item[1]["url"] for item in result]
        assert urls == ["https://a.com", "https://b.com", "https://c.com"]
        # Verify first occurrence kept (News 1, not News 1 Again)
        assert result[0][1]["title"] == "News 1"

    def test_field_info_preserved(self):
        """Field information (first element of tuple) preserved."""
        items = [
            ("news", {"title": "News", "url": "https://a.com"}),
            ("repos", {"title": "Repo", "url": "https://b.com"}),
        ]
        result = notify_telegram.first_items(items, n=2)
        assert result[0][0] == "news"
        assert result[1][0] == "repos"

    def test_empty_list(self):
        """Empty item list."""
        result = notify_telegram.first_items([], n=3)
        assert len(result) == 0

    def test_n_equals_one(self):
        """n=1 returns first item."""
        items = [
            ("news", {"title": "News 1", "url": "https://a.com"}),
            ("news", {"title": "News 2", "url": "https://b.com"}),
        ]
        result = notify_telegram.first_items(items, n=1)
        assert len(result) == 1
        assert result[0][1]["url"] == "https://a.com"

    def test_fewer_items_than_n(self):
        """Fewer items than n returns all."""
        items = [
            ("news", {"title": "News 1", "url": "https://a.com"}),
            ("news", {"title": "News 2", "url": "https://b.com"}),
        ]
        result = notify_telegram.first_items(items, n=10)
        assert len(result) == 2

    def test_all_duplicates(self):
        """All items have same URL."""
        items = [
            ("news", {"title": "News 1", "url": "https://a.com"}),
            ("news", {"title": "News 1 Alt", "url": "https://a.com"}),
            ("news", {"title": "News 1 v3", "url": "https://a.com"}),
        ]
        result = notify_telegram.first_items(items, n=3)
        assert len(result) == 1
        assert result[0][1]["title"] == "News 1"

    def test_dedup_across_sections(self):
        """Dedup works across different sections (field types)."""
        items = [
            ("news", {"title": "News", "url": "https://shared.com"}),
            ("repos", {"title": "Repo", "url": "https://other.com"}),
            ("events", {"title": "Event", "url": "https://shared.com"}),  # Same URL as news
        ]
        result = notify_telegram.first_items(items, n=3)
        assert len(result) == 2
        assert result[0][0] == "news"
        assert result[1][0] == "repos"

    def test_topic_order_preserved(self):
        """Topics appear in the order they appear in items."""
        items = [
            ("repos", {"title": "Repo 1", "url": "https://r1.com"}),
            ("news", {"title": "News 1", "url": "https://n1.com"}),
            ("repos", {"title": "Repo 2", "url": "https://r2.com"}),
        ]
        result = notify_telegram.first_items(items, n=3)
        assert result[0][0] == "repos"
        assert result[1][0] == "news"
        assert result[2][0] == "repos"
