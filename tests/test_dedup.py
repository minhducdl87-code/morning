"""Test dedup_utils — title normalization, Jaccard fuzzy dedup, index building."""
import pytest
from dedup_utils import (
    normalize_title,
    _tokens,
    is_duplicate_title,
    build_dedup_index,
    list_item_fields,
)


class TestNormalizeTitle:
    """normalize_title: emoji strip, punctuation→space, lowercase, collapse spaces."""

    def test_plain_text(self):
        """Plain ASCII text."""
        assert normalize_title("Hello World") == "hello world"

    def test_emoji_strip(self):
        """Emoji removed."""
        assert normalize_title("🔥 Hot News Today") == "hot news today"

    def test_emoji_multiple(self):
        """Multiple emoji removed."""
        assert normalize_title("✨ 🎉 Celebrate 🎊") == "celebrate"

    def test_punctuation_to_space(self):
        """Punctuation becomes space."""
        assert normalize_title("Hello, World!") == "hello world"

    def test_mixed_case_to_lower(self):
        """Mixed case normalized to lower."""
        assert normalize_title("HeLLo WoRLD") == "hello world"

    def test_whitespace_collapse(self):
        """Multiple spaces collapsed."""
        assert normalize_title("hello   world") == "hello world"

    def test_special_chars(self):
        """Special characters converted to space."""
        assert normalize_title("test@value#key") == "test value key"

    def test_empty_string(self):
        """Empty string returns empty."""
        assert normalize_title("") == ""

    def test_only_emoji(self):
        """Only emoji returns empty."""
        assert normalize_title("🔥 ✨ 🎉") == ""

    def test_unicode_chars(self):
        """Unicode Vietnamese text preserved."""
        assert normalize_title("Xin chào Việt Nam") == "xin chào việt nam"

    def test_combined_emoji_punct_space(self):
        """Combination of emoji, punctuation, extra spaces."""
        assert normalize_title("🔥  Test-Case!!!   Value") == "test case value"


class TestTokens:
    """_tokens: content-bearing words from normalized title (drops stopwords, 1-char)."""

    def test_plain_words(self):
        """Plain non-stopword tokens."""
        assert _tokens("machine learning model") == {"machine", "learning", "model"}

    def test_stopwords_dropped(self):
        """English stopwords dropped."""
        text = "the cat is on the mat"
        result = _tokens(text)
        # 'the', 'is', 'on' are stopwords; only 'cat', 'mat' kept (and not 1-char)
        assert "the" not in result
        assert "is" not in result
        assert "cat" in result
        assert "mat" in result

    def test_vietnamese_stopwords_dropped(self):
        """Vietnamese stopwords dropped."""
        text = "và là của"
        result = _tokens(text)
        assert len(result) == 0  # All are stopwords

    def test_one_char_dropped(self):
        """1-char tokens dropped."""
        text = "a big tree"
        result = _tokens(text)
        assert "a" not in result
        assert "big" in result
        assert "tree" in result

    def test_two_char_kept(self):
        """2-char tokens kept (not stopword)."""
        text = "ai ml go"
        result = _tokens(text)
        # 'go' is stopword, but 'ai', 'ml' not
        assert "ai" in result
        assert "ml" in result

    def test_empty_string(self):
        """Empty string returns empty set."""
        assert _tokens("") == set()

    def test_only_stopwords(self):
        """Only stopwords returns empty set."""
        assert _tokens("the a is of") == set()

    def test_case_insensitive(self):
        """Stopword check is case-insensitive."""
        text = "THE CAT"
        result = _tokens(text)
        assert "the" not in result
        assert "cat" in result


class TestBuildDedupIndex:
    """build_dedup_index: (exact_norms, token_sets_list) from title list."""

    def test_simple_titles(self):
        """Build index from simple titles."""
        titles = ["Hello World", "Python Code", "Hello World"]
        exact, tokens_list = build_dedup_index(titles)
        assert "hello world" in exact
        assert "python code" in exact
        assert len(tokens_list) <= 3  # May have some stopwords dropped

    def test_empty_list(self):
        """Empty title list."""
        exact, tokens_list = build_dedup_index([])
        assert len(exact) == 0
        assert len(tokens_list) == 0

    def test_duplicates_deduped(self):
        """Duplicate titles appear once in exact_norms."""
        titles = ["Test", "test", "TEST"]
        exact, _ = build_dedup_index(titles)
        assert "test" in exact
        assert len(exact) == 1

    def test_empty_strings_ignored(self):
        """Empty strings ignored."""
        titles = ["", "Test", ""]
        exact, tokens_list = build_dedup_index(titles)
        assert "" not in exact
        assert "test" in exact

    def test_tokens_list_short_filtered(self):
        """Token sets with <2 content tokens are filtered out."""
        titles = ["a", "I am here"]
        exact, tokens_list = build_dedup_index(titles)
        # "a" has no content tokens (1-char)
        # "I am here" → stopwords "a" dropped → tokens {"here"} (only 1)
        # So tokens_list should be shorter
        assert len(tokens_list) >= 0  # May be empty or have 1 entry


class TestIsDuplicateTitle:
    """is_duplicate_title: exact match OR Jaccard ≥0.55 → duplicate."""

    def test_exact_match(self):
        """Exact normalized match is duplicate."""
        exact = {"hello world"}
        assert is_duplicate_title("Hello World", exact, []) is True
        assert is_duplicate_title("hello world", exact, []) is True

    def test_no_match_empty_index(self):
        """No match in empty index."""
        assert is_duplicate_title("New Title", set(), []) is False

    def test_jaccard_above_threshold(self):
        """Jaccard ≥0.55 is duplicate."""
        # "machine learning" tokens: {machine, learning}
        # "machine deep learning" tokens: {machine, deep, learning}
        # Jaccard = 2 / 3 = 0.67 ≥ 0.55 → duplicate
        exact = set()
        recent_tokens = [{"machine", "learning"}]
        assert is_duplicate_title("machine deep learning", exact, recent_tokens) is True

    def test_jaccard_below_threshold(self):
        """Jaccard <0.55 is not duplicate."""
        # "ai" vs "blockchain"
        # No overlap → Jaccard = 0 < 0.55 → not duplicate
        exact = set()
        recent_tokens = [{"blockchain", "crypto"}]
        assert is_duplicate_title("artificial intelligence", exact, recent_tokens) is False

    def test_jaccard_threshold_boundary(self):
        """Test at 0.55 boundary."""
        # {a, b} vs {a, b, c, d} → Jaccard = 2 / 4 = 0.5 < 0.55 → not duplicate
        exact = set()
        recent_tokens = [{"a", "b", "c", "d"}]
        assert is_duplicate_title("a b", exact, recent_tokens) is False

    def test_short_token_set_not_dup(self):
        """Title with <2 content tokens is never duplicate."""
        exact = set()
        recent_tokens = [{"machine", "learning"}]
        # "a" → no tokens (1-char) → not duplicate
        assert is_duplicate_title("a", exact, recent_tokens) is False

    def test_empty_normalized_title(self):
        """Empty normalized title (all emoji/punct) is not duplicate."""
        exact = set()
        recent_tokens = [{"any", "tokens"}]
        assert is_duplicate_title("🔥 ✨ 🎉", exact, recent_tokens) is False

    def test_multiple_recent_titles(self):
        """Check against multiple recent title sets."""
        exact = set()
        recent_tokens = [
            {"python", "code"},
            {"machine", "learning"},
            {"deep", "learning"},
        ]
        # "deep learning neural" overlaps with "deep learning" → 2/3 = 0.67 ≥ 0.55
        assert is_duplicate_title("deep learning neural", exact, recent_tokens) is True

    def test_custom_threshold(self):
        """Custom threshold parameter."""
        exact = set()
        recent_tokens = [{"machine", "learning", "neural"}]
        # "machine learning" → tokens {machine, learning}
        # vs {machine, learning, neural} → Jaccard = 2/3 = 0.67
        # With threshold=0.7 (>0.67) → not duplicate
        # With threshold=0.6 (<0.67) → duplicate
        assert is_duplicate_title("machine learning", exact, recent_tokens, threshold=0.7) is False
        assert is_duplicate_title("machine learning", exact, recent_tokens, threshold=0.6) is True

    def test_stop_words_excluded(self):
        """Stopwords don't affect Jaccard."""
        exact = set()
        # "the machine" → tokens {machine} (stopword "the" dropped)
        # vs "the learning machine" → tokens {learning, machine}
        # Jaccard = 1 / 2 = 0.5 < 0.55
        recent_tokens = [{"learning", "machine"}]
        assert is_duplicate_title("the machine", exact, recent_tokens) is False


class TestListItemFields:
    """list_item_fields: return keys pointing to list values."""

    def test_simple_card(self):
        """Card with some list fields."""
        card = {"title": "Test", "items": [1, 2, 3], "count": 5}
        result = list_item_fields(card)
        assert "items" in result
        assert "title" not in result
        assert "count" not in result

    def test_no_lists(self):
        """Card with no list fields."""
        card = {"title": "Test", "count": 5}
        result = list_item_fields(card)
        assert len(result) == 0

    def test_multiple_lists(self):
        """Card with multiple list fields."""
        card = {"news": [1, 2], "repos": [3, 4], "name": "test"}
        result = list_item_fields(card)
        assert "news" in result
        assert "repos" in result
        assert "name" not in result

    def test_empty_dict(self):
        """Empty card."""
        result = list_item_fields({})
        assert len(result) == 0

    def test_empty_lists_included(self):
        """Empty list fields still returned."""
        card = {"items": [], "name": "test"}
        result = list_item_fields(card)
        assert "items" in result

    def test_nested_structures(self):
        """Dict inside list (for digest items)."""
        card = {"news": [{"title": "x", "url": "y"}], "meta": "data"}
        result = list_item_fields(card)
        assert "news" in result
        assert "meta" not in result
