# Review Final (INTEGRATION) — Refactor 4 track "Cá Mặn Đau Lưng"

Ngày: 2026-07-13 | Scope: toàn bộ diff refactor (25 file sửa + ~30 file mới) | Mode: review-only

## Verdict tổng: **PASS-with-issues**

Tích hợp 4 track OK về runtime & deploy. Không có circular import, không lỗi src, không reference chết, không đè file chéo track. **Một vấn đề High: `npx tsc --noEmit` FAIL (56 lỗi, 100% nằm trong `bot/src/__tests__/`)** — không chặn deploy/CI nhưng làm hỏng lưới an toàn type + lệnh verify.

---

## Kết quả các lệnh verify (thực chạy)

| Lệnh | Kết quả |
|------|---------|
| `python -m py_compile` (14 file .py) | PASS |
| Import 8 module mới + facade re-export | PASS (digest_utils re-export đủ: batch_check_urls, validate_*, GITHUB_REPO_RE, list_item_fields, is_url_live…) |
| Runtime import scrub_cards / notify-telegram | PASS |
| `python -m pytest tests/ -q` | **121 passed** |
| `node --check` (4 file JS FE) | PASS 4/4 |
| `cd bot && npm test` (vitest) | **64 passed** (5 file) |
| `cd bot && npx tsc --noEmit` | **FAIL — exit 2, 56 lỗi TS, tất cả trong `__tests__`, 0 lỗi trong src** |
| grep `digest.js` trong index.html/_headers | Không còn (đã xoá sạch) |
| CI có chạy tsc/vitest/pytest? | **KHÔNG** — 3 workflow chỉ deploy, không có gate typecheck/test → tsc fail không chặn pipeline |

---

## Findings

### HIGH-1 — `tsc --noEmit` fail: test files không compile (Track B↔D mismatch + thiếu type env)
`bot/tsconfig.json` có `include: ["src/**/*.ts"]` (kéo cả `__tests__`) và `types: ["@cloudflare/workers-types"]` (loại node + vitest globals). Hệ quả 2 nhóm lỗi:

**(a) Thiếu global types** — `bot/src/__tests__/http.test.ts` + `telegram.test.ts`:
- `TS2304: Cannot find name 'global'` (http.test.ts:16,20,25…; telegram.test.ts:54…)
- `TS2304: Cannot find name 'beforeEach'` (telegram.test.ts:53)
- Nguyên nhân: `global` cần `@types/node`; `beforeEach` cần vitest globals cho tsc (dù `globals:true` chỉ tác dụng lúc chạy vitest, không tác dụng với tsc).
- **Fix đề xuất (1 trong 3):**
  1. Loại test khỏi tsconfig chính: thêm `"exclude": ["src/__tests__"]` — nhanh, KISS. Hoặc
  2. `types: ["@cloudflare/workers-types", "vitest/globals", "node"]` + `npm i -D @types/node`. Hoặc
  3. Trong test dùng `globalThis` thay `global` và import `{ beforeEach }` từ `'vitest'`.

**(b) rag.test.ts fixtures lệch type mới (Track B đổi type, Track D viết theo type cũ)** — lỗi thật:
- `DigestData` giờ bắt buộc `config: any` nhưng fixtures thiếu → `TS2741` tại rag.test.ts:8,14,62,90,101,123,144.
- `WeeklyCard` giờ bắt buộc `fromDate, toDate` nhưng fixture chỉ có `weekLabel` → `TS2739` tại rag.test.ts:45.
- Runtime PASS vì `rag.ts` **không đọc** `.config` (đã verify) và type bị erase — nên test vẫn xanh, che mất lệch type.
- **Fix:** cập nhật fixtures trong `bot/src/__tests__/rag.test.ts`: thêm `config: {}` vào các object `DigestData`, thêm `fromDate/toDate` vào object `WeeklyCard` (dòng ~45).

**Đánh giá mức độ:** High cho type-safety/hygiene, **KHÔNG chặn deploy** (wrangler dùng esbuild bundle từ `index.ts`, không typecheck, không gồm file test) và **KHÔNG chặn CI** (không workflow nào chạy tsc). Không phải Critical.

---

## Các trục tích hợp đã kiểm — ĐẠT

**Python (facade & imports):** `scrub_cards` import qua facade `digest_utils` OK; `generate_card/weekly/monthly` import trực tiếp module mới (gemini_client, json_extract, prompt_builder, time_utils, dedup_utils, url_check, monthly_ranking) OK; không circular. facade re-export đủ symbol consumer cần.

**Frontend:** `index.html` nạp `styles.css` + 4 JS đúng thứ tự phụ thuộc `date-week-utils → renderers → view-builder → router-init` (dòng 12,37-40). FE dùng hàm global (script cổ điển, không module) — thứ tự đúng nên `router-init.init()` gọi `renderActiveView()` (view-builder) và view-builder gọi renderers resolve tại call-time OK. `_headers` cho phép `/*.js` `/*.css` (cache 300s), không chặn. Không còn `digest.js`.

**Bot wiring:** `index.ts → assertEnv/handleUpdate(router) → handlers/*`. Mọi import router resolve: `access.ts` tồn tại, 5 handler export đúng tên (transcribeVoice, handlePhoto, routeCommand, tryUrlSummary, handleChat). `PRIORITY_TAGS` đã xoá sạch khỏi bot. `wrangler.toml` hợp lệ, placeholder `REPLACE_WITH_KV_NAMESPACE_ID` khớp `sed` trong deploy-bot.yml (YAML/bash đúng cú pháp). Secrets/KV id đã chuyển ra placeholder/secret.

**Cross-track:** tập file 3 track tách theo thư mục rời nhau (root .py / bot / FE root) → không đè file chéo. `config.json` hợp lệ UTF-8 (keys: site, telegram, topics, tone_guidance); Python đọc `encoding="utf-8"`, FE `loadConfig()` fetch `config.json` đọc `topics` — nhất quán.

**Regression hành vi:** `notify-telegram` `first_items()` thay `PRIORITY_TAGS` chạy đúng cả 2 mode — `build_morning_message` dùng `first_items(all_items,3)`, `build_recap_message` dùng `first_items(collect_items(card),3)`; không vỡ. Format cards/weekly/monthly.json không đổi (generate_* chỉ tách module, giữ output).

---

## Positive
- Tách module sạch, facade backward-compat chuẩn (zero breakage cho consumer cũ).
- Bảo mật: chuyển ALLOWED_CHAT_IDS + KV id sang secret/placeholder cho repo public — tốt.
- 185 test (121 py + 64 vitest) đều xanh; env-guard/http-timeout/multipart fix có test bao phủ.

## Recommended Actions (ưu tiên)
1. **[High]** Sửa `tsc --noEmit`: chọn HIGH-1(a) fix (khuyến nghị option 1: `exclude: ["src/__tests__"]` — nhanh nhất) **và** HIGH-1(b) cập nhật fixtures rag.test.ts cho khớp type mới. (b) nên làm dù chọn cách nào để giữ đúng type Track B.
2. **[Low]** Cân nhắc thêm 1 gate `tsc --noEmit` + `vitest` vào CI bot để lần sau bắt được lệch type sớm.

## Câu hỏi mở
- Có chủ ý để test files nằm trong tsconfig chính không, hay muốn tách `tsconfig.test.json` riêng? Ảnh hưởng cách fix HIGH-1(a).
- `DigestData.config: any` — có kế hoạch siết type cho `config` không, hay giữ `any` là cố ý (YAGNI)?
