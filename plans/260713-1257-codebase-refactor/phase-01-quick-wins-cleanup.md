# Phase 01 — Quick Wins & Dọn Rác

## Context Links
- Report Python: `plans/reports/reviewer-python-260713-1257-codebase-refactor.md` (M2, M4, M6, M1-doc, L1, L2, L4)
- Report Bot: `plans/reports/reviewer-bot-260713-1257-codebase-refactor.md` (M4, L3, L5)

## Overview
- **Priority:** P1 (làm trước — mở đường cho P2)
- **Status:** partial — Python phần (Track A) completed; index.html/bot phần thuộc Track B/C
- **Effort:** ~3h — Quick win, rủi ro thấp
- Dọn dead code, chống crash, đồng bộ doc/config. Không đổi kiến trúc.

## Key Insights
- `title_prefix()` (digest_utils.py:45-48) không caller — dead code (đã grep).
- `c["date"]` truy cập trực tiếp → 1 card thiếu `date` crash cả run daily/weekly.
- `recent_prefixes` thực chất là token-sets → tên gây hiểu nhầm khi refactor dedup.
- Monthly docstring nói dùng Gemini nhưng code KHÔNG import genai (concept chết) — chỉ sửa DOC (không đổi hành vi); quyết định có LLM hay không là câu hỏi mở #1.

## Requirements
- Functional: hành vi output không đổi (trừ việc không còn crash khi thiếu `date`).
- Non-functional: giảm clutter, doc khớp code.

## Related Code Files
**Sửa:**
- `digest_utils.py` — xoá `title_prefix()` (M2); sync docstring threshold 0.55 (L4).
- `generate_card.py` — `.get("date")` guard + skip (M6, dòng ~260); đổi `recent_prefixes`→`recent_tokens` (M4, dòng 41/248); sửa comment "first-5-word prefix" (dòng ~237).
- `generate_weekly.py` — `.get("date")` guard (M6, dòng ~30).
- `generate_monthly.py` — sync docstring khớp "aggregate-only" (M1-doc, dòng 9-10).
- `index.html` — bỏ chuỗi giờ hardcode "5h/5AM" (L2, dòng ~329/341), để config.json quyết.
- `bot/src/telegram.ts` — `esc()` thêm `"`→`&quot;` (L3-bot).
- `bot/src/commands.ts` + `bot/README.md` — gỡ mục "Ảnh → em mô tả" khỏi menu /start + README (M4-bot, mặc định gỡ theo YAGNI; chờ Q#7).

**Xoá:**
- `config.claude-original.json` (L1) — hoặc chuyển `docs/` (chờ Q#3).

**Tạo:** không.

## Implementation Steps
1. Grep xác nhận `title_prefix` 0 caller → xoá hàm + import liên quan.
2. Sửa `strptime(c["date"],…)` → dùng `c.get("date")`; nếu None → `continue`/skip (mẫu digest_utils.py:108-110). Áp cho card + weekly.
3. Đổi tên biến `recent_prefixes`→`recent_tokens` toàn `generate_card.py`; sửa comment mô tả cơ chế cũ.
4. Sync docstring: monthly (aggregate-only), threshold 0.55 (digest_utils.py:80).
5. Xoá chuỗi giờ tĩnh trong index.html; xác nhận `loadConfig()` vẫn ghi footer/title từ config.
6. `esc()`: thêm replace `"`→`&quot;`.
7. Gỡ dòng "Ảnh → mô tả" ở commands.ts menu + README (chờ xác nhận Q#7; nếu Anh muốn giữ → chuyển sang P3 implement).
8. Xử lý `config.claude-original.json` theo Q#3 (mặc định xoá).

## Todo
- [x] Xoá `title_prefix()` + verify không vỡ import (0 caller, xoá khỏi digest_utils.py)
- [x] `.get("date")` guard trong generate_card.py + generate_weekly.py (áp cả generate_monthly.py load path)
- [x] Đổi tên `recent_prefixes`→`recent_tokens` + sửa comment (thực hiện trong lúc viết lại generate_card.py orchestrator — comment "first-5-word prefix" đã bỏ)
- [x] Sync docstring monthly + threshold 0.55 (digest_utils threshold doc + generate_monthly docstring: no LLM, aggregate-only cả 2 mode)
- [ ] Bỏ giờ hardcode index.html — NGOÀI SCOPE Track A (Python), thuộc Track C (frontend)
- [ ] esc() escape `"` — NGOÀI SCOPE Track A (bot/src/telegram.ts thuộc Track B)
- [ ] Gỡ/giữ mục mô tả ảnh — NGOÀI SCOPE Track A (bot thuộc Track B)
- [x] Xử lý config.claude-original.json — MOVE vào `docs/config.claude-original.json` (theo quyết định user, verify 0 code reference trước khi move)

## Success Criteria
- `python generate_card.py` chạy với env giả (hoặc dry-run tới bước strptime) không crash khi cards.json chèn 1 card thiếu `date`.
- Grep `title_prefix` → 0 kết quả; `recent_prefixes` → 0 kết quả.
- `index.html` mở trong browser: footer/title/giờ lấy từ config.json, không còn "5AM" tĩnh.
- Bot `tsc --noEmit` pass sau sửa esc()/menu.

## Risk
- Thấp. Rủi ro duy nhất: bỏ nhầm chuỗi giờ mà `loadConfig()` không ghi đè element đó → kiểm DOM element id trước khi xoá.

## Security Considerations
- `esc()` `"` escape = giảm HTML-attribute injection từ URL không kiểm soát (digest/user).

## Next Steps
- Mở khoá P2 (Python refactor) — biến `recent_tokens` + date-guard đã sạch.
- Chờ Anh trả lời Q#1 (monthly LLM), Q#3 (config-original), Q#7 (mô tả ảnh) trước khi finalize step 4/7/8.
