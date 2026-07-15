"""Test evening_update.run_evening — guards (no morning card yet / already done)
+ merge-into-today's-card logic. Gemini/HTTP/file-write calls mocked, no network,
no real cards.json touched."""
from datetime import datetime
from unittest.mock import patch

import evening_update
from time_utils import VN_TZ


def _now(date_str: str = "2026-07-15") -> datetime:
    return datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=VN_TZ)


def _topics() -> dict:
    return {
        "tech": {
            "output_field": "tech", "data_source": "jina",
            "min_items": 1, "max_items": 3,
            "prompt_instruction": "x", "schema": "{}",
        },
    }


class TestGuards:
    """Skip (return False) when there's no morning card yet, or evening already done."""

    def test_no_cards_at_all_skip(self):
        assert evening_update.run_evening({}, _topics(), [], _now()) is False

    def test_morning_card_not_today_skip(self):
        cards = [{"date": "2026-07-14", "tech": []}]
        assert evening_update.run_evening({}, _topics(), cards, _now()) is False

    def test_already_done_skip(self):
        cards = [{"date": "2026-07-15", "tech": [], "eveningDone": True}]
        assert evening_update.run_evening({}, _topics(), cards, _now()) is False


class TestMerge:
    """New survivors get appended to today's card with addedEvening=true; morning
    items are left untouched; eveningDone flag set; cards.json write is mocked."""

    @patch("evening_update.write_cards_file")
    @patch("evening_update.dedup_card")
    @patch("evening_update.validate_card")
    @patch("evening_update.generate_card_json")
    @patch("evening_update.fetch_contexts")
    def test_merge_new_items(self, mock_fetch, mock_gen, mock_validate, mock_dedup, mock_write):
        cards = [{
            "date": "2026-07-15", "dayLabel": "Thứ Tư", "dateLabel": "15/07/2026",
            "tech": [{"title": "Old tech news", "url": "https://a.com", "desc": "",
                       "tag": "x", "tagLabel": "X", "source": "s"}],
        }]
        mock_fetch.return_value = ({"tech": "ctx"}, {"https://b.com"})
        mock_gen.return_value = {
            "date": "2026-07-15",
            "tech": [{"title": "New tech news", "url": "https://b.com", "desc": "",
                       "tag": "x", "tagLabel": "X", "source": "s"}],
        }
        mock_validate.side_effect = lambda c, *a, **k: c
        mock_dedup.side_effect = lambda c, *a, **k: c

        result = evening_update.run_evening({}, _topics(), cards, _now())

        assert result is True
        assert cards[0]["eveningDone"] is True
        assert len(cards[0]["tech"]) == 2
        assert cards[0]["tech"][0].get("addedEvening") is None  # morning item untouched
        assert cards[0]["tech"][1]["addedEvening"] is True
        mock_write.assert_called_once_with(cards)

    @patch("evening_update.write_cards_file")
    @patch("evening_update.dedup_card")
    @patch("evening_update.validate_card")
    @patch("evening_update.generate_card_json")
    @patch("evening_update.fetch_contexts")
    def test_all_deduped_still_marks_done(self, mock_fetch, mock_gen, mock_validate, mock_dedup, mock_write):
        cards = [{"date": "2026-07-15", "dayLabel": "Thứ Tư", "dateLabel": "15/07/2026", "tech": []}]
        mock_fetch.return_value = ({}, set())
        mock_gen.return_value = {"date": "2026-07-15", "tech": []}
        mock_validate.side_effect = lambda c, *a, **k: c
        mock_dedup.side_effect = lambda c, *a, **k: c

        result = evening_update.run_evening({}, _topics(), cards, _now())

        assert result is True
        assert cards[0]["eveningDone"] is True
        assert cards[0]["tech"] == []
        mock_write.assert_called_once_with(cards)

    @patch("evening_update.write_cards_file")
    @patch("evening_update.dedup_card")
    @patch("evening_update.validate_card")
    @patch("evening_update.generate_card_json")
    @patch("evening_update.fetch_contexts")
    def test_dedup_receives_today_titles_and_urls(self, mock_fetch, mock_gen, mock_validate, mock_dedup, mock_write):
        """Evening dedup context must include today's own morning items (not just
        the 7-day-excluding-today window) so it doesn't re-add the same story."""
        cards = [{
            "date": "2026-07-15", "dayLabel": "Thứ Tư", "dateLabel": "15/07/2026",
            "tech": [{"title": "Morning story", "url": "https://a.com"}],
        }]
        mock_fetch.return_value = ({}, set())
        mock_gen.return_value = {"date": "2026-07-15", "tech": []}
        mock_validate.side_effect = lambda c, *a, **k: c
        mock_dedup.side_effect = lambda c, *a, **k: c

        evening_update.run_evening({}, _topics(), cards, _now())

        dedup_call_args = mock_dedup.call_args
        recent_urls = dedup_call_args[0][2]
        assert "https://a.com" in recent_urls
