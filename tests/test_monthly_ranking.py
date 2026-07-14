"""Test monthly_ranking — dedup by URL, rank news and repos."""
import pytest
from monthly_ranking import dedupe_by_url, rank_news, rank_repos


class TestDedupeByUrl:
    """dedupe_by_url: keep first occurrence per URL (chronologically earliest)."""

    def test_no_duplicates(self):
        """No duplicate URLs."""
        items = [
            {"url": "https://a.com", "title": "A"},
            {"url": "https://b.com", "title": "B"},
        ]
        result = dedupe_by_url(items)
        assert len(result) == 2
        assert result[0]["url"] == "https://a.com"
        assert result[1]["url"] == "https://b.com"

    def test_duplicate_urls_keep_first(self):
        """Duplicate URLs keep first occurrence."""
        items = [
            {"url": "https://example.com", "title": "First"},
            {"url": "https://other.com", "title": "Other"},
            {"url": "https://example.com", "title": "Duplicate"},
        ]
        result = dedupe_by_url(items)
        assert len(result) == 2
        assert result[0]["title"] == "First"
        assert result[1]["title"] == "Other"

    def test_multiple_duplicates(self):
        """Multiple items with same URL."""
        items = [
            {"url": "https://a.com", "title": "A1"},
            {"url": "https://a.com", "title": "A2"},
            {"url": "https://a.com", "title": "A3"},
        ]
        result = dedupe_by_url(items)
        assert len(result) == 1
        assert result[0]["title"] == "A1"

    def test_empty_url_ignored(self):
        """Items with no/empty URL are ignored."""
        items = [
            {"url": "", "title": "NoURL"},
            {"url": "https://a.com", "title": "A"},
        ]
        result = dedupe_by_url(items)
        assert len(result) == 1
        assert result[0]["url"] == "https://a.com"

    def test_missing_url_key_ignored(self):
        """Items without URL key are ignored."""
        items = [
            {"title": "NoKey"},
            {"url": "https://a.com", "title": "A"},
        ]
        result = dedupe_by_url(items)
        assert len(result) == 1

    def test_order_preserved(self):
        """Order of first occurrences preserved."""
        items = [
            {"url": "https://z.com", "title": "Z"},
            {"url": "https://a.com", "title": "A"},
            {"url": "https://z.com", "title": "Z2"},
            {"url": "https://m.com", "title": "M"},
        ]
        result = dedupe_by_url(items)
        assert len(result) == 3
        assert result[0]["url"] == "https://z.com"
        assert result[1]["url"] == "https://a.com"
        assert result[2]["url"] == "https://m.com"

    def test_empty_list(self):
        """Empty item list."""
        result = dedupe_by_url([])
        assert len(result) == 0


class TestRankNews:
    """rank_news: sort by priority tag then recency, drop helper fields."""

    def test_priority_ranking(self):
        """Items ranked by priority tag."""
        items = [
            {"title": "API", "tag": "api", "_date": "2024-01-05"},
            {"title": "Hot", "tag": "hot", "_date": "2024-01-01"},
            {"title": "Feature", "tag": "feature", "_date": "2024-01-03"},
        ]
        result = rank_news(items)
        # Expected order: hot (0), feature (3), api (4)
        assert result[0]["tag"] == "hot"
        assert result[1]["tag"] == "feature"
        assert result[2]["tag"] == "api"

    def test_within_priority_sort_by_recency(self):
        """Within same priority, sort by recency (earliest first per _date)."""
        items = [
            {"title": "Old", "tag": "api", "_date": "2024-01-10"},
            {"title": "New", "tag": "api", "_date": "2024-01-05"},
        ]
        result = rank_news(items)
        assert len(result) == 2
        # Both are "api" (priority 4), sorted by _date ascending
        # Helper fields (_date) are dropped in output
        assert result[0]["title"] == "New"  # 2024-01-05 is earlier
        assert result[1]["title"] == "Old"  # 2024-01-10 is later
        assert "_date" not in result[0]  # Helper fields removed

    def test_unknown_tag_priority_9(self):
        """Unknown tags get priority 9 (lowest)."""
        items = [
            {"title": "Unknown", "tag": "unknown", "_date": "2024-01-01"},
            {"title": "Hot", "tag": "hot", "_date": "2024-01-02"},
        ]
        result = rank_news(items)
        # hot (0) comes before unknown (9)
        assert result[0]["tag"] == "hot"
        assert result[1]["tag"] == "unknown"

    def test_helper_fields_dropped(self):
        """Fields starting with _ are dropped."""
        items = [
            {"title": "News", "tag": "hot", "_date": "2024-01-01", "_internal": "data"},
        ]
        result = rank_news(items)
        assert "_date" not in result[0]
        assert "_internal" not in result[0]
        assert "title" in result[0]

    def test_top_n_limit(self):
        """Only top N items returned (default 10)."""
        items = [{"title": f"Item {i}", "tag": "api", "_date": "2024-01-01"} for i in range(15)]
        result = rank_news(items, top_n=10)
        assert len(result) == 10

    def test_custom_top_n(self):
        """Custom top_n parameter."""
        items = [{"title": f"Item {i}", "tag": "api", "_date": "2024-01-01"} for i in range(5)]
        result = rank_news(items, top_n=3)
        assert len(result) == 3

    def test_fewer_items_than_top_n(self):
        """Fewer items than top_n returns all."""
        items = [
            {"title": "A", "tag": "hot", "_date": "2024-01-01"},
            {"title": "B", "tag": "api", "_date": "2024-01-02"},
        ]
        result = rank_news(items, top_n=10)
        assert len(result) == 2

    def test_empty_list(self):
        """Empty item list."""
        result = rank_news([])
        assert len(result) == 0

    def test_missing_tag_key(self):
        """Items without tag key get priority 9."""
        items = [
            {"title": "NoTag", "_date": "2024-01-01"},
            {"title": "Hot", "tag": "hot", "_date": "2024-01-02"},
        ]
        result = rank_news(items)
        # hot should come first
        assert result[0]["tag"] == "hot"


class TestRankRepos:
    """rank_repos: verdict=yes first, then by stars (parsed from '12K+')."""

    def test_verdict_ranking(self):
        """Repos ranked by verdict (yes < maybe < skip)."""
        items = [
            {"url": "https://skip.com", "verdict": "skip", "stars": "1K"},
            {"url": "https://yes.com", "verdict": "yes", "stars": "100"},
            {"url": "https://maybe.com", "verdict": "maybe", "stars": "500"},
        ]
        result = rank_repos(items)
        assert result[0]["verdict"] == "yes"
        assert result[1]["verdict"] == "maybe"
        assert result[2]["verdict"] == "skip"

    def test_stars_ranking_within_verdict(self):
        """Within same verdict, rank by stars (descending)."""
        items = [
            {"url": "https://a.com", "verdict": "yes", "stars": "500"},
            {"url": "https://b.com", "verdict": "yes", "stars": "1K"},
            {"url": "https://c.com", "verdict": "yes", "stars": "100"},
        ]
        result = rank_repos(items)
        # 1K > 500 > 100
        assert result[0]["stars"] == "1K"
        assert result[1]["stars"] == "500"
        assert result[2]["stars"] == "100"

    def test_stars_parsing_k_suffix(self):
        """Stars with K suffix parsed (1K = 1000)."""
        items = [
            {"url": "https://a.com", "verdict": "yes", "stars": "10K"},
            {"url": "https://b.com", "verdict": "yes", "stars": "5K"},
        ]
        result = rank_repos(items)
        assert result[0]["stars"] == "10K"
        assert result[1]["stars"] == "5K"

    def test_stars_parsing_k_plus_suffix(self):
        """Stars with K+ suffix parsed."""
        items = [
            {"url": "https://a.com", "verdict": "yes", "stars": "10K+"},
            {"url": "https://b.com", "verdict": "yes", "stars": "5K+"},
        ]
        result = rank_repos(items)
        assert result[0]["stars"] == "10K+"

    def test_stars_parsing_no_suffix(self):
        """Stars without suffix (plain number)."""
        items = [
            {"url": "https://a.com", "verdict": "yes", "stars": "1000"},
            {"url": "https://b.com", "verdict": "yes", "stars": "500"},
        ]
        result = rank_repos(items)
        assert result[0]["stars"] == "1000"

    def test_stars_parsing_invalid(self):
        """Invalid stars string defaults to 0."""
        items = [
            {"url": "https://a.com", "verdict": "yes", "stars": "invalid"},
            {"url": "https://b.com", "verdict": "yes", "stars": "100"},
        ]
        result = rank_repos(items)
        # 100 > 0, so b comes first
        assert result[0]["stars"] == "100"

    def test_missing_stars(self):
        """Missing stars defaults to 0."""
        items = [
            {"url": "https://a.com", "verdict": "yes"},
            {"url": "https://b.com", "verdict": "yes", "stars": "100"},
        ]
        result = rank_repos(items)
        assert result[0]["stars"] == "100"

    def test_helper_fields_dropped(self):
        """Fields starting with _ are dropped."""
        items = [
            {"url": "https://a.com", "verdict": "yes", "stars": "100", "_rank": "internal"},
        ]
        result = rank_repos(items)
        assert "_rank" not in result[0]
        assert "url" in result[0]

    def test_top_n_limit(self):
        """Only top N repos returned (default 8)."""
        items = [{"url": f"https://{i}.com", "verdict": "yes", "stars": f"{i*100}"} for i in range(15)]
        result = rank_repos(items, top_n=8)
        assert len(result) == 8

    def test_custom_top_n(self):
        """Custom top_n parameter."""
        items = [{"url": f"https://{i}.com", "verdict": "yes", "stars": f"{i*100}"} for i in range(5)]
        result = rank_repos(items, top_n=3)
        assert len(result) == 3

    def test_empty_list(self):
        """Empty repo list."""
        result = rank_repos([])
        assert len(result) == 0

    def test_missing_verdict_key(self):
        """Items without verdict key get priority 3 (skip)."""
        items = [
            {"url": "https://no-verdict.com", "stars": "1K"},
            {"url": "https://yes.com", "verdict": "yes", "stars": "100"},
        ]
        result = rank_repos(items)
        assert result[0]["verdict"] == "yes"
