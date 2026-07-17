import unittest

from prompt_builder import build_daily_prompt
from card_pipeline import sanitize_reader_detail, validate_card


class PromptBuilderDetailContractTests(unittest.TestCase):
    def test_daily_prompt_requires_distinct_summary_and_reader_detail(self):
        topics = {
            "tech": {
                "output_field": "tech",
                "min_items": 1,
                "max_items": 1,
                "prompt_instruction": "Tin công nghệ có nguồn.",
                "schema": '{"title":"","desc":"","detail":"","source":"","url":""}',
            }
        }

        prompt = build_daily_prompt(
            topics=topics,
            recent_titles=[],
            topic_contexts={"tech": "Nguồn kiểm thử"},
            day_label="Thứ Năm",
            date_label="16/07/2026",
            date_str="2026-07-16",
            dedup_days=7,
        )

        self.assertIn("detail 3-5 câu", prompt)
        self.assertIn("không lặp nguyên văn desc", prompt)

    def test_duplicate_detail_is_removed_but_distinct_detail_survives(self):
        repeated = {"desc": "Tin có bối cảnh và tác động rõ.", "detail": "Tin có bối cảnh và tác động rõ."}
        distinct = {
            "desc": "Giá vàng tăng trong phiên sáng.",
            "detail": "Đà tăng diễn ra sau biến động của thị trường quốc tế. Chênh lệch mua bán vẫn ở mức đáng lưu ý. Người mua tích lũy nên theo dõi giá trước khi quyết định.",
        }
        prefixed = {
            "desc": "Giá vàng tăng trong phiên sáng.",
            "detail": "Giá vàng tăng trong phiên sáng. Thị trường quốc tế biến động. Chênh lệch mua bán vẫn cao.",
        }

        self.assertNotIn("detail", sanitize_reader_detail(repeated))
        self.assertIn("detail", sanitize_reader_detail(distinct))
        self.assertNotIn("detail", sanitize_reader_detail(prefixed))

    def test_validation_pipeline_preserves_distinct_reader_detail(self):
        source_url = "https://example.com/news/story"
        card = {
            "tech": [{
                "title": "A sourced product update",
                "desc": "A short summary for scanning.",
                "detail": (
                    "The release follows a limited pilot with office users. "
                    "It changes how teams review shared work. "
                    "Readers should compare the rollout terms before adopting it."
                ),
                "url": source_url,
            }]
        }

        validated = validate_card(
            card_json=card,
            output_fields=["tech"],
            repo_fields=[],
            trusted_urls={source_url},
        )

        self.assertEqual(len(validated["tech"]), 1)
        self.assertIn("detail", validated["tech"][0])
        self.assertNotEqual(validated["tech"][0]["detail"], validated["tech"][0]["desc"])


if __name__ == "__main__":
    unittest.main()
