# Phase 06 — Test Coverage Pure Functions

## Context Links
- Report Python: `plans/reports/reviewer-python-260713-1257-codebase-refactor.md` (Metrics — test coverage 0%)
- Report Bot: `plans/reports/reviewer-bot-260713-1257-codebase-refactor.md` (R1/R2 làm code testable)
- Phụ thuộc: **Phase 02** (module Python testable) + **Phase 04** (handlers bot testable).

## Overview
- **Priority:** P2 (làm cuối, sau khi code ổn định)
- **Status:** pending
- **Effort:** ~5h
- Đặt nền test cho **pure functions** (không mạng, không LLM). Không có framework sẵn → setup pytest + vitest.

## Key Insights
- Cả 2 hệ hiện **0% coverage**, không có test framework (`package.json` bot không có test script; không có `requirements.txt`/pytest).
- Chỉ test pure/deterministic để tránh phụ thuộc mạng — YAGNI, không test call LLM thật.
- Test **verify behavior-preserving** cho các phase trước (chốt output logic dedup/parse/split).

## Requirements
- Functional: test chạy xanh; cover các hàm thuần chính.
- Non-functional: chạy được local + (tuỳ chọn) trong CI; không cần secret/mạng.

## Related Code Files
**Tạo (Python — pytest):**
- `requirements-dev.txt` — `pytest`.
- `tests/test_dedup.py` — normalize_title, `_tokens`, jaccard, is_duplicate_title, build_dedup_index (digest_utils).
- `tests/test_url_check.py` — validate_news_items/validate_repo_items logic (mock HEAD), format_stars nếu có.
- `tests/test_json_extract.py` — `parse_llm_json`: fence, JSON thuần, có text thừa, rác→None (module từ P2).
- `tests/test_list_fields.py` — `list_item_fields` bỏ date/dayLabel/dateLabel.

**Tạo (Bot — vitest):**
- `bot/package.json` — thêm `vitest` devDep + `"test": "vitest run"`.
- `bot/src/__tests__/rag.test.ts` — retrieve/dedup URL + stopwords VN, no-query fallback.
- `bot/src/__tests__/telegram-split.test.ts` — `sendLongMessage` chunk ≤4096 ranh giới dòng (từ P3).
- `bot/src/__tests__/telegram-types.test.ts` — `isMessageUpdate` guard (từ P4).
- `bot/src/__tests__/esc.test.ts` — escape `<>&"`.

## Implementation Steps
1. Python: `pip install pytest`; viết test cho pure functions; chạy `pytest -q`.
2. Chọn hàm KHÔNG chạm mạng (dedup, json-extract, list-fields, format). URL-check: mock `is_url_live`.
3. Bot: thêm vitest; viết test rag/split/guard/esc; `npm test` (bot).
4. (Tuỳ chọn) thêm step CI: `pytest` vào `morning.yml`? — CHỜ xác nhận (có thể làm chậm cron). Mặc định chỉ chạy local/PR, không chèn vào cron sản xuất.
5. Ghi coverage baseline (mục tiêu pure-function core, không ép %).

## Todo
- [ ] pytest setup + requirements-dev.txt
- [ ] test_dedup, test_url_check, test_json_extract, test_list_fields
- [ ] vitest setup trong bot/package.json
- [ ] rag / telegram-split / types-guard / esc tests
- [ ] pytest -q xanh; npm test (bot) xanh

## Success Criteria
- `pytest -q` pass toàn bộ; `npm test` (bot) pass.
- Test bắt được regression: cố ý đổi 1 hàm dedup → test đỏ.
- Không test nào cần secret/mạng thật.

## Risk
- Thấp. Rủi ro: import path Python sau P2 chưa ổn → chạy P6 SAU P2 hoàn tất.
- vitest + workers-types: cấu hình môi trường test (node) tách khỏi Worker runtime; mock KV/fetch nơi cần.

## Security Considerations
- Test dùng fixture/mock, KHÔNG chứa API key thật.

## Next Steps
- Sau xanh: cân nhắc thêm test gate vào PR workflow (không vào cron `morning.yml`).
- Là chốt cuối xác nhận toàn bộ refactor behavior-preserving.
