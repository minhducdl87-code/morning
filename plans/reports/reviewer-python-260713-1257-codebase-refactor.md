# Code Review — Pipeline Python + Web "Cá Mặn Đau Lưng" (Morning Digest)

Review-only, định hướng REFACTOR. Ngày: 2026-07-13. Reviewer: code-reviewer.
Phạm vi: `generate_card.py`, `digest_utils.py`, `jina_fetch.py`, `rss_fetch.py`, `generate_weekly.py`, `generate_monthly.py`, `notify-telegram.py`, `scrub_cards.py`, `digest.js`, `index.html`, `config.json`, `config.claude-original.json`. KHÔNG động `bot/`.

---

## Tóm tắt

Pipeline hoạt động tốt, kiến trúc "topic-agnostic" (đọc field động từ list) là điểm mạnh — cho phép đổi bộ chủ đề mà không sửa renderer. Nợ kỹ thuật **trung bình**, chủ yếu là **DRY** (logic lặp qua 3 generator) và **tách concern** (`generate_card.py` là script phẳng 267 dòng trộn mọi thứ, không có `main()`, không testable). Không có bug nghiêm trọng gây mất dữ liệu, nhưng có vài edge case crash được (KeyError date), dead code, doc sai lệch code, và 1 file backup thừa.

Số file > 200 LOC: `generate_card.py` (267), `generate_monthly.py` (226), `digest_utils.py` (212), `generate_weekly.py` (203), `digest.js` (363), `index.html` (345, ~300 là CSS inline).

Vai trò `digest.js`: **frontend renderer trên browser** (load qua `<script src="digest.js">` ở index.html:342), đọc `cards/weekly/monthly.json` để render. **KHÔNG trùng logic sinh dữ liệu với Python** → không phải 2 nguồn sự thật về *generation*. NHƯNG trùng *vocabulary trình bày* (nhãn/emoji section, MONTHS_VI, map field legacy) với `notify-telegram.py` + `generate_monthly.py` → xem Findings DRY.

---

## Findings

### Critical
Không có.

### High

**H1 — `generate_card.py` là script phẳng, không tách concern, không testable** (`generate_card.py` toàn bộ)
Toàn bộ chạy ở module-level: load config → fetch → build prompt → call Gemini → parse JSON → HEAD-check → validate → dedup → ghi file. Không `main()`, không hàm bọc → không import/test được, khó tái dùng. Đây là ứng viên refactor lớn nhất. Đề xuất tách module (xem "Cơ hội refactor lớn").

**H2 — `call_gemini` + parse-JSON + strip-fence lặp giữa card và weekly** (`generate_card.py:117-163, 189-213` ↔ `generate_weekly.py:98-151`)
Hai bản `call_gemini` gần trùng (khác param: card có `use_search`/grounding, weekly `thinking_budget=0`). Khối `re.sub(r"^```...")` + `json.loads` → regex `\{[\s\S]+\}` fallback lặp y hệt. Gom vào `gemini-client.py` (call + retry + extract) và `json-extract.py` (strip fence + parse fallback → dict|None).

**H3 — Setup timezone lặp 3 lần** (`generate_card.py:14-19`, `generate_weekly.py:10-15`, `generate_monthly.py:20-25`)
Khối `try: import zoneinfo … except ImportError: tz=utc` copy-paste 3 file. Đưa vào `digest_utils` (hoặc `time-utils.py`): `from digest_utils import VN_TZ, now_vn()`.

**H4 — `_list_fields` / list-fields logic lặp ≥5 nơi** (`digest_utils.py:21`, `scrub_cards.py:9`, inline ở `generate_weekly.py:48-49`, `generate_monthly.py:58-59`, `notify-telegram.py:51-52`, `digest.js:99`)
Cùng logic "lấy key trỏ tới list, bỏ date/dayLabel/dateLabel". `scrub_cards.py` định nghĩa lại y hệt bản trong `digest_utils`. Python: import 1 hàm duy nhất `list_item_fields(card)`. JS giữ bản riêng (chấp nhận được vì khác runtime).

### Medium

**M1 — Doc sai code: monthly "summarise via Gemini" nhưng KHÔNG có Gemini** (`generate_monthly.py:9-10`)
Docstring nói "summarise via Gemini if key available, otherwise aggregate-only fallback". Thực tế file **không import genai**, không gọi LLM — chỉ aggregate + rank + HEAD-check. Workflow monthly cũng không set `GEMINI_API_KEY` / không `pip install google-genai`. → Đây là concept chết trong doc. Sửa docstring cho khớp (thuần aggregate) HOẶC quyết định có thật sự cần LLM summarise không (YAGNI: hiện aggregate là đủ và an toàn hơn).

**M2 — Dead code: `title_prefix()` không được dùng** (`digest_utils.py:45-48`)
Đã grep toàn repo: chỉ định nghĩa, không caller. Dedup hiện dùng `_tokens` + Jaccard chứ không dùng prefix. Xoá (YAGNI). Kèm: comment `generate_card.py:237` vẫn ghi "first-5-word prefix" — mô tả cơ chế cũ đã bỏ.

**M3 — `all_valid_urls` whitelist gần như vô dụng** (`generate_card.py:108-110, 176-177`)
`valid_urls_per_topic` gom thành `all_valid_urls` nhưng **chỉ dùng cho `has_data` (bool) + print**; validation cuối cùng dựa HEAD-check trực tiếp (`batch_check_urls`) chứ không enforce whitelist. → Cả cỗ máy gom URL per-topic là over-engineer. `fetch_topic_context` chỉ cần trả `(ctx, bool has_urls)`. Giảm state, đơn giản hoá (KISS).

**M4 — Biến `recent_prefixes` đặt tên sai nghĩa** (`generate_card.py:41, 248`)
`build_dedup_index` trả `(exact_norms, tokens_list)` nhưng unpack thành `recent_norms, recent_prefixes`. Thực chất là token-sets, không phải prefix. Gây hiểu nhầm khi refactor dedup. Đổi tên `recent_tokens`.

**M5 — `PRIORITY_TAGS` trong notify lệch với tag config hiện tại** (`notify-telegram.py:36`)
`PRIORITY_TAGS = {hot, launch, stock, crypto, policy, economy, movie, review}`. Config hiện dùng tag `launch|review|ai|deal` (tech), `stock|crypto|gold|realestate|rate` (finance)… Nhiều tag mới (`ai`, `deal`, `gold`, `health`, `food`…) không có trong map → rơi về 99 → "Top 3 không thể bỏ qua" gần như chỉ theo thứ tự xuất hiện, không thật sự ưu tiên. `hot` thậm chí không tồn tại trong config mới. → Coupling ngầm config↔notify. Đề xuất: đọc priority từ config.json (thêm field `priority` per-topic) thay vì hardcode.

**M6 — Edge case crash: card thiếu key `date`** (`generate_card.py:260`, `generate_weekly.py:30`)
`datetime.strptime(c["date"], …)` truy cập trực tiếp `c["date"]` không try/except (khác với `get_recent_titles` đã phòng KeyError). 1 card lỗi/thiếu date trong `cards.json` → crash cả lần chạy daily/weekly. Dùng `.get("date")` + skip an toàn (đã có mẫu ở `digest_utils.py:108-110`).

**M7 — `index.html` 345 dòng, ~300 là CSS inline** (`index.html:13-317`)
Rule dự án <200 LOC. Tách CSS ra `styles.css` (`<link>`) — giảm index.html còn ~50 dòng HTML thuần, dễ đọc/diff. App chỉ còn 1 onclick inline (`toggleToc`), có thể chuyển sang addEventListener trong digest.js.

**M8 — `digest.js` 363 dòng, đơn khối** (`digest.js`)
Plain script không bundler. Tách logic thành nhiều file nạp tuần tự qua nhiều `<script>` (không cần build step): `date-week-utils.js` (35-62), `renderers.js` (73-172), `view-builder.js` (176-231), `router-init.js` (còn lại). Giữ nguyên global functions để tránh module loader.

### Low

**L1 — File backup thừa `config.claude-original.json`** (không được reference bất kỳ đâu ngoài git index)
Là bản config gốc (news/repos/gamingNews). Không code nào đọc. Git history đã giữ. → Xoá khỏi working tree (clutter) hoặc chuyển vào `docs/`.

**L2 — Nhãn giờ lệch giữa index.html tĩnh và config.json** (`index.html:329,341` "5h/5AM" ↔ `config.json:4,6` "9h/9AM")
`loadConfig()` ghi đè footer + title từ config, nhưng chuỗi tĩnh "Sáng 5h/5AM" trong HTML là giá trị stale (cron thực = 9AM VN). Tagline element lại bị `init()` ghi đè bằng số đếm ngày/tuần/tháng. → Nguồn sự thật duy nhất nên là config.json; bỏ chuỗi giờ hardcode trong HTML.

**L3 — `MONTHS_VI` + map section/emoji lặp Python↔JS** (`generate_monthly.py:28`, `digest.js:4`; `notify-telegram.py:39-44 section_meta` ↔ `digest.js:17-31 sectionMeta`)
config.json là nguồn sự thật (emoji/section_label per topic), nhưng cả Python và JS đều có bản fallback "legacy" riêng cho field cũ (news/repos/gamingNews). Chấp nhận được (2 runtime), nhưng nên tài liệu hoá field legacy ở 1 chỗ để tránh drift.

**L4 — Docstring threshold sai số** (`digest_utils.py:80`) "Threshold 0.6 = 60%" nhưng default param = `0.55`. Đồng bộ lại.

**L5 — Naming file Python dùng snake_case + 1 file dùng kebab** (`notify-telegram.py` vs `generate_card.py`)
Rule dự án gợi kebab-case, nhưng module Python import bằng `_` (không import được nếu có `-`). `notify-telegram.py` không bị import (chạy standalone) nên OK. **KHÔNG đề xuất đổi** — các file được import (`digest_utils`, `jina_fetch`, `rss_fetch`) buộc dùng `_`, đổi sẽ vỡ import + workflow. Chỉ note để planner biết ràng buộc.

---

## Cơ hội refactor lớn (nhóm theo module đề xuất)

**Tách `generate_card.py` (267) → orchestrator mỏng + modules:**
- `gemini-client.py` — `call_gemini(prompt, use_search, thinking_budget, retries)` dùng chung card + weekly (giải H2). Bao gồm extract text-part (bỏ `thought`) + grounding citations.
- `json-extract.py` — `parse_llm_json(text) -> dict|None` (strip ```fence + json.loads + regex fallback), dùng chung card + weekly (giải H2).
- `prompt-builder.py` — `build_daily_prompt(...)` (hiện `generate_card.py:45-94`).
- `card-pipeline.py` hoặc giữ `generate_card.py` làm `main()` mỏng: load → fetch → prompt → call → parse → validate → dedup → write. Mỗi bước 1 hàm, có `if __name__ == "__main__"`.
- Chuyển timezone + `list_item_fields` vào `digest_utils` (giải H3, H4).

**Kết quả:** card/weekly cùng dùng `gemini-client` + `json-extract`; mỗi file < 150 LOC, testable.

**`digest_utils.py` (212):** đang gánh nhiều concern (dedup + URL-liveness + validation). Có thể tách `dedup.py` (normalize/tokens/jaccard/get_recent_*) và `url-check.py` (is_url_live/batch/validate_*), giữ `digest_utils` re-export. Ưu tiên thấp hơn vì đã là pure functions testable.

**Frontend:** tách CSS (M7) + chia digest.js (M8).

---

## Vai trò `digest.js` — kết luận

- Dùng DUY NHẤT tại `index.html:342` (`<script src="digest.js">`). Không reference trong workflow/markdown.
- Là **client-side renderer** (ToC + hash router + render card daily/weekly/monthly). Đọc JSON output của pipeline Python.
- **Không hợp nhất được với Python** (khác runtime: browser vs CI). Không phải duplicate logic *generation*.
- Điểm cần dọn: trùng *vocabulary trình bày* với Python (L3) — nên coi config.json là nguồn sự thật, và tài liệu hoá danh sách field legacy 1 chỗ.
- **Không đề xuất loại bỏ.**

---

## Quick wins vs Refactor lớn

**Quick wins (effort thấp, ít rủi ro):**
- Xoá `title_prefix` dead code (M2).
- Xoá/di dời `config.claude-original.json` (L1).
- Fix `.get("date")` chống crash (M6).
- Đổi tên `recent_prefixes`→`recent_tokens` (M4).
- Sync docstring monthly + threshold (M1 doc-phần, L4).
- Bỏ chuỗi giờ hardcode HTML, để config quyết (L2).

**Refactor lớn (cần plan + test):**
- Tách `generate_card.py` + rút `gemini-client`/`json-extract` chung (H1, H2).
- Gom timezone + list-fields vào digest_utils (H3, H4).
- Đơn giản hoá whitelist URL (M3).
- Đọc priority tags từ config (M5).
- Tách CSS + chia digest.js (M7, M8).

---

## Điểm tốt (giữ nguyên)

- Kiến trúc topic-agnostic (list-field động) rất linh hoạt — đổi chủ đề chỉ sửa config.json.
- HARD RULES chống Gemini bịa URL + HEAD-check song song + strict-drop dead URL: chống fake-news tốt.
- Fallback Gemini + Google Search grounding khi thiếu data (`generate_card.py:166-174`).
- `notify-telegram.py`: gửi nhiều chat_id, partial-failure không chặn recipient khác; exit code hợp lý.
- Monthly backfill aggregate-only "no fake-news risk" — thiết kế an toàn có chủ đích.
- Rolling window (30 ngày cards / 12 tuần / 12 tháng) gọn.

---

## Metrics
- Type coverage (Python type hints): ~70% hàm có annotation, tốt.
- Test coverage: **0%** — không có test nào. Refactor lớn nên kèm test cho pure functions (dedup, url-check, json-extract, format_stars, month_bounds).
- Dead code: `title_prefix` (1 hàm), `config.claude-original.json` (1 file), whitelist URL (phần lớn vô dụng).
- File > 200 LOC: 5 (card, monthly, digest_utils, weekly, digest.js) + index.html (CSS).

---

## Câu hỏi chưa giải đáp

1. Monthly có thật sự muốn LLM-summarise (như docstring) hay aggregate-only là chủ đích cuối? Ảnh hưởng quyết định M1.
2. `config.claude-original.json` giữ làm template tham khảo hay xoá hẳn? (git history đã có).
3. Thứ tự ưu tiên "Top 3" của Telegram có quan trọng với Anh không? Nếu có → nên đưa `priority` vào config (M5); nếu không → bỏ `PRIORITY_TAGS` cho gọn.
4. Frontend split (M7/M8): chấp nhận nhiều `<script>`/`<link>` tag (no bundler) hay muốn giữ tối giản số file? Ảnh hưởng cách tách.
5. Giờ chạy thực tế là 9AM (cron) — chuỗi "5AM" trong index.html là stale hay có ý đồ? (L2).
