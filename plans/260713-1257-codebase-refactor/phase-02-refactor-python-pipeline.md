# Phase 02 — Refactor Pipeline Python

## Context Links
- Report Python: `plans/reports/reviewer-python-260713-1257-codebase-refactor.md` (H1, H2, H3, H4, M3, "Cơ hội refactor lớn")
- Phụ thuộc: **Phase 01** (biến `recent_tokens`, date-guard đã sạch)

## Overview
- **Priority:** P1 (refactor lớn)
- **Status:** completed (Track A — Python pipeline refactor)
- **Effort:** ~6h — Refactor lớn, cần test verify
- Tách `generate_card.py` (267) thành orchestrator mỏng + module chung dùng lại cho weekly. Gom timezone + list-fields. Đơn giản hoá whitelist URL.

## Key Insights
- `call_gemini` + strip-fence + parse-JSON lặp gần trùng card↔weekly (H2) → rút chung.
- Timezone setup copy-paste 3 file (H3); `_list_fields` lặp ≥5 nơi, scrub_cards định nghĩa lại (H4).
- `all_valid_urls` whitelist chỉ dùng làm bool `has_data` — validation cuối bằng HEAD-check trực tiếp → over-engineer (M3, KISS).
- Ràng buộc: file được import PHẢI snake_case (không kebab) nếu không vỡ `import`. → module mới đặt `.py` snake_case (vd `gemini_client.py`, `json_extract.py`, `prompt_builder.py`, `time_utils.py`), KHÔNG kebab-case như rule chung.

## Requirements
- Functional: output `cards.json`/`weekly.json` **giống hệt** trước refactor với cùng input (byte-diff hoặc field-diff).
- Non-functional: mỗi file < 200 LOC (mục tiêu < 150); các bước có hàm bọc, testable, có `if __name__ == "__main__"`.

## Related Code Files
**Tạo:**
- `gemini_client.py` — `call_gemini(prompt, use_search=False, thinking_budget=None, retries=...)` dùng chung card+weekly; extract text-part (bỏ `thought`), grounding citations (H2).
- `json_extract.py` — `parse_llm_json(text) -> dict|None` (strip ```fence + json.loads + regex `\{[\s\S]+\}` fallback) (H2).
- `prompt_builder.py` — `build_daily_prompt(...)` (chuyển từ generate_card.py:45-94).
- `time_utils.py` — `VN_TZ`, `now_vn()` (hoặc đặt trong digest_utils; H3). Chọn 1, thống nhất import.

**Sửa:**
- `generate_card.py` → orchestrator mỏng: `main()` gọi load→fetch→prompt→call→parse→validate→dedup→write; mỗi bước 1 hàm; `if __name__`. Dùng module mới. `fetch_topic_context` trả `(ctx, has_urls: bool)` thay vì gom whitelist (M3).
- `generate_weekly.py` — thay bản `call_gemini`/parse riêng bằng import `gemini_client`+`json_extract`; dùng `time_utils`.
- `generate_monthly.py` — dùng `time_utils` (H3).
- `digest_utils.py` — thêm/export `list_item_fields(card)` 1 nguồn (H4); (tuỳ chọn) re-export tz.
- `scrub_cards.py` — bỏ bản `_list_fields` riêng, import `list_item_fields` (H4).
- `jina_fetch.py` — điều chỉnh signature nếu `fetch_topic_context` đổi return (M3).

**Xoá:** logic gom `valid_urls_per_topic`/`all_valid_urls` nếu chỉ phục vụ bool (M3).

## Implementation Steps
1. Tạo `json_extract.py`, viết `parse_llm_json`; thay 2 chỗ strip-fence+parse (card+weekly) bằng gọi hàm.
2. Tạo `gemini_client.py`, hợp nhất 2 `call_gemini` (param hoá `use_search`/`thinking_budget`); giữ nguyên retry + grounding.
3. Tạo `time_utils.py` (`VN_TZ`, `now_vn()`); thay 3 khối tz copy-paste.
4. Thêm `list_item_fields()` vào digest_utils; sửa scrub_cards + inline weekly/monthly/notify import dùng chung.
5. Chuyển `build_prompt`→`prompt_builder.build_daily_prompt`.
6. Refactor `generate_card.py` thành `main()` + hàm con; thêm `if __name__ == "__main__": main()`.
7. Đơn giản hoá M3: `fetch_topic_context` → `(ctx, has_urls)`; bỏ máy gom whitelist.
8. Compile check: `python -c "import generate_card, generate_weekly, generate_monthly, gemini_client, json_extract, prompt_builder"`.

## Todo
- [x] json_extract.py + thay card/weekly
- [x] gemini_client.py + hợp nhất call_gemini (lazy client singleton, param hoá use_search/thinking_budget/max_output_tokens)
- [x] time_utils.py + thay 3 tz block (card/weekly/monthly)
- [x] list_item_fields() 1 nguồn + sửa scrub_cards (+ notify-telegram, generate_monthly, generate_weekly dùng luôn)
- [x] prompt_builder.py
- [x] generate_card.py → main() mỏng + hàm con
- [x] M3 whitelist → (ctx, has_urls) — fetch_topic_context trong jina_fetch.py trả bool, generate_card.py bỏ hẳn all_valid_urls bookkeeping
- [x] Import/compile check pass; mỗi file < 200 LOC (thêm split digest_utils.py→dedup_utils.py+url_check.py, generate_monthly.py→monthly_ranking.py để giữ <200 LOC theo rule global)

**Ngoài phạm vi ban đầu của phase (theo chỉ đạo user, đã thực hiện trong Track A):**
- [x] Remove Top-3 PRIORITY_TAGS trong notify-telegram.py (gây loop bug, stale vs config tags) → thay bằng `first_items()` lấy N item đầu theo thứ tự topic, không ranking

## Success Criteria
- Chạy `generate_card.py` local (env `GEMINI_API_KEY` giả + mock/record 1 response, hoặc real key) → `cards.json` mới **diff = 0 field khác biệt logic** so với baseline (lưu baseline trước refactor).
- Tương tự `generate_weekly.py` → `weekly.json` không đổi.
- Tất cả module import được (chuẩn bị cho P6 test).
- `wc -l` mỗi file Python < 200.

## Risk
- Trung. Đổi return của `fetch_topic_context` (M3) đụng jina_fetch → verify has_data bool vẫn đúng nhánh fallback Gemini-search.
- `call_gemini` hợp nhất: param khác biệt (grounding vs thinking_budget) — giữ default sao cho card=grounding on, weekly=thinking_budget 0. Test cả 2 path.
- **Mitigation:** snapshot `cards.json`/`weekly.json` trước; so field-by-field sau.

## Security Considerations
- Giữ nguyên HARD RULES chống Gemini bịa URL + HEAD-check song song + strict-drop dead URL (điểm mạnh, không được suy giảm).
- `GEMINI_API_KEY` chỉ đọc từ env, không log.

## Next Steps
- Mở khoá P6 (test pure functions: `parse_llm_json`, `list_item_fields`, dedup, url-check).
- Nếu CI `morning.yml` gọi trực tiếp `python generate_card.py` (không đổi tên file) → không cần sửa workflow; xác nhận trước.
