"""Test url_check — GitHub regex, item validation (mock live checks), liveness policy."""
import socket
import urllib.error
from unittest.mock import patch

import pytest
from url_check import (
    GITHUB_REPO_RE,
    is_url_live,
    validate_news_items,
    validate_repo_items,
)


class TestGitHubRepoRegex:
    """GITHUB_REPO_RE matches github.com/owner/repo format."""

    def test_valid_github_url(self):
        """Valid GitHub repo URL."""
        assert GITHUB_REPO_RE.match("https://github.com/openai/gpt-3") is not None

    def test_valid_github_trailing_slash(self):
        """Valid GitHub repo URL with trailing slash."""
        assert GITHUB_REPO_RE.match("https://github.com/openai/gpt-3/") is not None

    def test_invalid_no_owner(self):
        """No owner/repo structure."""
        assert GITHUB_REPO_RE.match("https://github.com/") is None

    def test_invalid_only_owner(self):
        """Only owner, no repo."""
        assert GITHUB_REPO_RE.match("https://github.com/openai") is None

    def test_invalid_too_many_parts(self):
        """Too many path segments."""
        assert GITHUB_REPO_RE.match("https://github.com/openai/gpt-3/issues") is None

    def test_invalid_no_https(self):
        """HTTP instead of HTTPS."""
        assert GITHUB_REPO_RE.match("http://github.com/openai/gpt-3") is None

    def test_invalid_github_gist(self):
        """GitHub gist URL (different domain)."""
        assert GITHUB_REPO_RE.match("https://gist.github.com/user/abc123") is None

    def test_invalid_space_in_path(self):
        """Space in URL."""
        assert GITHUB_REPO_RE.match("https://github.com/open ai/gpt-3") is None

    def test_invalid_not_github(self):
        """Non-GitHub URL."""
        assert GITHUB_REPO_RE.match("https://gitlab.com/openai/gpt-3") is None

    def test_valid_hyphenated_names(self):
        """Owner/repo with hyphens."""
        assert GITHUB_REPO_RE.match("https://github.com/my-org/my-repo") is not None

    def test_valid_underscore_names(self):
        """Owner/repo with underscores."""
        assert GITHUB_REPO_RE.match("https://github.com/my_org/my_repo") is not None

    def test_valid_numbers_in_names(self):
        """Owner/repo with numbers."""
        assert GITHUB_REPO_RE.match("https://github.com/org123/repo456") is not None


class TestValidateNewsItems:
    """validate_news_items: drop news without live URL."""

    def test_all_live_urls(self):
        """All items have live URLs."""
        items = [
            {"title": "News 1", "url": "https://example.com/1"},
            {"title": "News 2", "url": "https://example.com/2"},
        ]
        live_map = {
            "https://example.com/1": True,
            "https://example.com/2": True,
        }
        result = validate_news_items(items, live_map)
        assert len(result) == 2

    def test_drop_dead_url(self):
        """Drop item with dead URL."""
        items = [
            {"title": "News 1", "url": "https://dead.com"},
            {"title": "News 2", "url": "https://live.com"},
        ]
        live_map = {
            "https://dead.com": False,
            "https://live.com": True,
        }
        result = validate_news_items(items, live_map)
        assert len(result) == 1
        assert result[0]["url"] == "https://live.com"

    def test_drop_missing_url(self):
        """Drop item without URL."""
        items = [
            {"title": "News 1"},  # No URL
            {"title": "News 2", "url": "https://example.com"},
        ]
        live_map = {"https://example.com": True}
        result = validate_news_items(items, live_map)
        assert len(result) == 1

    def test_drop_empty_url(self):
        """Drop item with empty URL string."""
        items = [
            {"title": "News 1", "url": ""},
            {"title": "News 2", "url": "https://example.com"},
        ]
        live_map = {"https://example.com": True}
        result = validate_news_items(items, live_map)
        assert len(result) == 1

    def test_strip_whitespace_url(self):
        """URL with whitespace stripped before check."""
        items = [
            {"title": "News", "url": "  https://example.com  "},
        ]
        live_map = {"https://example.com": True}
        result = validate_news_items(items, live_map)
        # After strip, "https://example.com" is checked
        assert len(result) == 1

    def test_empty_list(self):
        """Empty item list."""
        result = validate_news_items([], {})
        assert len(result) == 0

    def test_url_not_in_live_map(self):
        """URL not in live_map defaults to False."""
        items = [{"title": "News", "url": "https://unknown.com"}]
        live_map = {}
        result = validate_news_items(items, live_map)
        assert len(result) == 0

    def test_trusted_url_bypasses_dead_live_map(self):
        """URL in trusted_urls is kept even if live_map marks it dead (false-negative
        HEAD-check, e.g. vnexpress blocking bot requests) — whitelist-trust fix."""
        items = [{"title": "News", "url": "https://vnexpress.net/rss/giai-tri/1.html"}]
        live_map = {"https://vnexpress.net/rss/giai-tri/1.html": False}
        trusted_urls = {"https://vnexpress.net/rss/giai-tri/1.html"}
        result = validate_news_items(items, live_map, trusted_urls)
        assert len(result) == 1

    def test_trusted_url_bypasses_missing_live_map_entry(self):
        """URL in trusted_urls is kept even if never HEAD-checked at all."""
        items = [{"title": "News", "url": "https://trusted.example.com/a"}]
        result = validate_news_items(items, {}, {"https://trusted.example.com/a"})
        assert len(result) == 1

    def test_untrusted_url_still_uses_live_map(self):
        """URL not in trusted_urls still follows normal live_map validation."""
        items = [
            {"title": "News 1", "url": "https://untrusted.com/dead"},
            {"title": "News 2", "url": "https://trusted.com/real"},
        ]
        live_map = {"https://untrusted.com/dead": False, "https://trusted.com/real": False}
        trusted_urls = {"https://trusted.com/real"}
        result = validate_news_items(items, live_map, trusted_urls)
        assert len(result) == 1
        assert result[0]["url"] == "https://trusted.com/real"

    def test_default_trusted_urls_is_backward_compatible(self):
        """Omitting trusted_urls (2-arg call) behaves exactly like before."""
        items = [{"title": "News", "url": "https://example.com"}]
        result = validate_news_items(items, {"https://example.com": False})
        assert len(result) == 0


class TestIsUrlLive:
    """is_url_live: benefit-of-doubt policy — only 404/410/DNS-fail/conn-refused are dead."""

    def test_empty_url(self):
        assert is_url_live("") is False

    def test_non_http_url(self):
        assert is_url_live("ftp://example.com") is False

    def test_url_with_space(self):
        assert is_url_live("https://example.com/a b") is False

    def test_blacklisted_domain(self):
        assert is_url_live("https://vertexaisearch.cloud.google.com/x") is False

    @patch("url_check.urllib.request.urlopen")
    def test_200_is_live(self, mock_urlopen):
        mock_urlopen.return_value.__enter__.return_value.status = 200
        assert is_url_live("https://example.com") is True

    @patch("url_check.urllib.request.urlopen")
    def test_404_is_dead(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.HTTPError(
            "https://example.com", 404, "Not Found", {}, None
        )
        assert is_url_live("https://example.com") is False

    @patch("url_check.urllib.request.urlopen")
    def test_410_is_dead(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.HTTPError(
            "https://example.com", 410, "Gone", {}, None
        )
        assert is_url_live("https://example.com") is False

    @patch("url_check.urllib.request.urlopen")
    def test_403_is_benefit_of_doubt(self, mock_urlopen):
        """403 (bot-block, e.g. vnexpress from CI IP) is NOT proof of dead — kept live."""
        mock_urlopen.side_effect = urllib.error.HTTPError(
            "https://example.com", 403, "Forbidden", {}, None
        )
        assert is_url_live("https://example.com") is True

    @patch("url_check.urllib.request.urlopen")
    def test_405_is_benefit_of_doubt(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.HTTPError(
            "https://example.com", 405, "Method Not Allowed", {}, None
        )
        assert is_url_live("https://example.com") is True

    @patch("url_check.urllib.request.urlopen")
    def test_429_is_benefit_of_doubt(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.HTTPError(
            "https://example.com", 429, "Too Many Requests", {}, None
        )
        assert is_url_live("https://example.com") is True

    @patch("url_check.urllib.request.urlopen")
    def test_dns_failure_is_dead(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.URLError(socket.gaierror("nodename not found"))
        assert is_url_live("https://nonexistent-domain.invalid") is False

    @patch("url_check.urllib.request.urlopen")
    def test_connection_refused_is_dead(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.URLError(ConnectionRefusedError())
        assert is_url_live("https://example.com") is False

    @patch("url_check.urllib.request.urlopen")
    def test_timeout_is_benefit_of_doubt(self, mock_urlopen):
        mock_urlopen.side_effect = TimeoutError("timed out")
        assert is_url_live("https://example.com") is True

    @patch("url_check.urllib.request.urlopen")
    def test_generic_urlerror_is_benefit_of_doubt(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.URLError("some transient network error")
        assert is_url_live("https://example.com") is True


class TestValidateRepoItems:
    """validate_repo_items: drop repos with bad format or dead URL."""

    def test_valid_github_repos(self):
        """Valid GitHub repos."""
        items = [
            {"url": "https://github.com/openai/gpt-3"},
            {"url": "https://github.com/google/tensorflow/"},
        ]
        live_map = {
            "https://github.com/openai/gpt-3": True,
            "https://github.com/google/tensorflow/": True,
        }
        result = validate_repo_items(items, live_map)
        assert len(result) == 2

    def test_drop_non_github_url(self):
        """Drop non-GitHub repo URLs."""
        items = [
            {"url": "https://gitlab.com/user/repo"},
            {"url": "https://github.com/user/repo"},
        ]
        live_map = {
            "https://gitlab.com/user/repo": True,
            "https://github.com/user/repo": True,
        }
        result = validate_repo_items(items, live_map)
        assert len(result) == 1
        assert "github.com" in result[0]["url"]

    def test_drop_dead_github_repo(self):
        """Drop GitHub repo with dead URL."""
        items = [
            {"url": "https://github.com/dead/repo"},
            {"url": "https://github.com/live/repo"},
        ]
        live_map = {
            "https://github.com/dead/repo": False,
            "https://github.com/live/repo": True,
        }
        result = validate_repo_items(items, live_map)
        assert len(result) == 1

    def test_drop_missing_url(self):
        """Drop repo without URL."""
        items = [
            {"name": "Repo 1"},
            {"url": "https://github.com/user/repo"},
        ]
        live_map = {"https://github.com/user/repo": True}
        result = validate_repo_items(items, live_map)
        assert len(result) == 1

    def test_drop_empty_url(self):
        """Drop repo with empty URL."""
        items = [
            {"url": ""},
            {"url": "https://github.com/user/repo"},
        ]
        live_map = {"https://github.com/user/repo": True}
        result = validate_repo_items(items, live_map)
        assert len(result) == 1

    def test_drop_incomplete_github_url(self):
        """Drop GitHub URLs without repo name."""
        items = [
            {"url": "https://github.com/user"},
            {"url": "https://github.com/user/repo"},
        ]
        live_map = {
            "https://github.com/user/repo": True,
        }
        result = validate_repo_items(items, live_map)
        assert len(result) == 1

    def test_empty_list(self):
        """Empty repo list."""
        result = validate_repo_items([], {})
        assert len(result) == 0

    def test_strip_whitespace_url(self):
        """URL with whitespace stripped before validation."""
        items = [
            {"url": "  https://github.com/user/repo  "},
        ]
        live_map = {"https://github.com/user/repo": True}
        result = validate_repo_items(items, live_map)
        assert len(result) == 1
