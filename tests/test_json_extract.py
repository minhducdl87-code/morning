"""Test parse_llm_json — JSON extraction from LLM text with markdown fence stripping."""
import pytest
from json_extract import parse_llm_json


class TestParseLlmJson:
    """parse_llm_json: fence stripping, direct parse, fallback regex, None on fail."""

    def test_json_plain(self):
        """Plain JSON object."""
        text = '{"key": "value"}'
        result = parse_llm_json(text)
        assert result == {"key": "value"}

    def test_json_with_fence_json(self):
        """JSON with ```json fence."""
        text = '```json\n{"key": "value"}\n```'
        result = parse_llm_json(text)
        assert result == {"key": "value"}

    def test_json_with_fence_no_lang(self):
        """JSON with ``` fence (no language)."""
        text = '```\n{"key": "value"}\n```'
        result = parse_llm_json(text)
        assert result == {"key": "value"}

    def test_json_with_text_before(self):
        """JSON with explanatory text before fence."""
        text = 'Here is the result:\n```json\n{"title": "test"}\n```'
        result = parse_llm_json(text)
        assert result == {"title": "test"}

    def test_json_with_text_after(self):
        """JSON with explanatory text after fence."""
        text = '```json\n{"count": 42}\n```\nThat is the answer.'
        result = parse_llm_json(text)
        assert result == {"count": 42}

    def test_json_nested(self):
        """Nested JSON structure."""
        text = '{"outer": {"inner": [1, 2, 3]}}'
        result = parse_llm_json(text)
        assert result == {"outer": {"inner": [1, 2, 3]}}

    def test_json_with_whitespace(self):
        """JSON with leading/trailing whitespace."""
        text = '  \n  {"key": "value"}  \n  '
        result = parse_llm_json(text)
        assert result == {"key": "value"}

    def test_json_with_fence_whitespace(self):
        """Fence with extra whitespace."""
        text = '```  json  \n{"key": "value"}\n```  '
        result = parse_llm_json(text)
        assert result == {"key": "value"}

    def test_json_invalid_returns_none(self):
        """Invalid JSON returns None."""
        text = '{invalid json}'
        result = parse_llm_json(text)
        assert result is None

    def test_json_empty_string_returns_none(self):
        """Empty string returns None."""
        result = parse_llm_json('')
        assert result is None

    def test_json_none_returns_none(self):
        """None input returns None."""
        result = parse_llm_json(None)  # type: ignore
        assert result is None

    def test_json_only_text_no_json_returns_none(self):
        """Pure text without JSON returns None."""
        text = 'This is just plain text without any JSON.'
        result = parse_llm_json(text)
        assert result is None

    def test_json_mixed_text_with_regex_fallback(self):
        """Text with embedded JSON (regex fallback)."""
        text = 'The result is {\"status\": \"ok\"} and that is it.'
        result = parse_llm_json(text)
        assert result == {"status": "ok"}

    def test_json_array_parses(self):
        """JSON array is parsed directly by json.loads (not just objects)."""
        text = '[1, 2, 3]'
        result = parse_llm_json(text)
        # Direct parse succeeds for arrays too
        assert result == [1, 2, 3]

    def test_json_with_unicode(self):
        """JSON with unicode characters."""
        text = '{"message": "Xin chào"}'
        result = parse_llm_json(text)
        assert result == {"message": "Xin chào"}

    def test_json_fence_with_spaces_inside(self):
        """Fence with various spacing."""
        text = '```json  \n{"key": "value"}\n  ```'
        result = parse_llm_json(text)
        assert result == {"key": "value"}
