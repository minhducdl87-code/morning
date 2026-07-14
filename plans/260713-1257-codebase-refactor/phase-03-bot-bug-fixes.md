# Phase 03 — Bot Bug Fixes Ưu Tiên

## Context Links
- Report Bot: `plans/reports/reviewer-bot-260713-1257-codebase-refactor.md` (H1, H2, H3, M6, M7, R3, R4)
- Độc lập với Python; nên làm trước Phase 04.

## Overview
- **Priority:** P1 (chứa 2 bug chức năng thật)
- **Status:** pending
- **Effort:** ~4h — Quick win + bug fix, rủi ro trung
- Sửa `/img` luôn fail, message >4096 bị nuốt, fetch không timeout, thêm assertEnv + báo lỗi user.

## Key Insights
- **H1:** `gpt-image-1` chỉ trả `b64_json`; code gửi data-URI qua field `photo` JSON → Telegram từ chối (chỉ nhận HTTP URL/file_id). `/img` luôn fail. Fix: `sendPhotoBlob` upload multipart/form-data (blob). (Chờ Q#2: giữ model hay đổi loại trả URL.)
- **H2:** `sendMessage` (telegram.ts:18) không cắt 4096 → digest/RAG/summary dài → `call()` null + im lặng. Fix: `sendLongMessage` chunk theo ranh giới dòng.
- **H3:** không fetch nào dùng AbortController → treo trong `waitUntil`. Fix: `fetchWithTimeout` chung (20s LLM, 10s Jina/Telegram).
- **M6:** thiếu API key chỉ lộ khi call → khó chẩn. `assertEnv(env)`.
- **M7:** `waitUntil` nuốt lỗi → user im lặng. Bọc try/catch trong handleUpdate gửi fallback.

## Requirements
- Functional: `/img` gửi được ảnh; reply dài không mất; timeout trả fallback thân thiện thay vì treo.
- Non-functional: không đổi persona/prompt; `strict` + `noImplicitAny` vẫn pass.

## Related Code Files
**Tạo:**
- `bot/src/http.ts` — `fetchWithTimeout(url, opts, ms)` + (tuỳ chọn) `fetchJson()` gom từ digest.ts, retry nhẹ 1 lần cho 5xx LLM (H3/R3).

**Sửa:**
- `bot/src/telegram.ts` — thêm `sendLongMessage()` (chunk 4096) + `sendPhotoBlob()` (multipart b64) (H2/H1/R4). Chuyển reply dài sang `sendLongMessage`.
- `bot/src/llm/openai.ts` — `/img` trả blob/bytes thay vì data-URI; hoặc đổi model (Q#2).
- `bot/src/index.ts` — điểm gọi `/img` (138-139) dùng `sendPhotoBlob`; bọc try/catch handleUpdate gửi fallback (M7); gọi `assertEnv` (M6).
- `bot/src/llm/gemini.ts`, `url-summary.ts`, `digest.ts` — dùng `fetchWithTimeout`.
- `bot/src/types.ts` hoặc `access.ts` — hàm `assertEnv(env)` kiểm biến bắt buộc (không log giá trị) (M6).

## Implementation Steps
1. Tạo `http.ts` `fetchWithTimeout` (AbortController + clearTimeout); thay mọi `fetch` LLM/Jina/Telegram.
2. `telegram.ts`: `sendLongMessage` — nếu text ≤4096 gửi thẳng; nếu > cắt theo `\n` gần 4096, gửi tuần tự. Thay các reply dài (digest/week/month/RAG/summary).
3. `telegram.ts`: `sendPhotoBlob(token, chatId, bytes, caption)` — FormData + Blob, POST sendPhoto multipart.
4. `openai.ts`: trả `Uint8Array`/base64 decode; index.ts:138-139 gọi `sendPhotoBlob`. (Nếu Q#2 = đổi model trả URL → dùng sendPhoto URL, bỏ blob.)
5. `assertEnv(env)`: kiểm `TELEGRAM_BOT_TOKEN`, `GEMINI_API_KEY`, (`OPENAI_API_KEY` nếu /img). Gọi đầu `fetch()`; thiếu → log rõ + trả 500.
6. `handleUpdate`: bọc try/catch tổng, catch → `sendMessage(chatId, "Có lỗi, Anh thử lại sau nhé")` (M7).
7. `tsc --noEmit` pass.

## Todo
- [x] http.ts fetchWithTimeout + thay toàn bộ fetch
- [x] sendLongMessage chunk 4096 + áp reply dài
- [x] sendPhotoBlob multipart + sửa /img
- [x] assertEnv env bắt buộc
- [x] try/catch handleUpdate báo lỗi user
- [x] tsc --noEmit pass

## Success Criteria
- `wrangler dev` + curl webhook payload `/img mèo` → ảnh về Telegram (hoặc test-chat) thành công.
- Curl payload `/digest` với digest dài > 4096 → nhận đủ nhiều message, không mất.
- Mô phỏng LLM chậm (URL không phản hồi) → sau ~20s user nhận fallback, Worker không treo.
- Thiếu 1 env → log rõ tên biến thiếu, không lộ giá trị.

## Risk
- Trung. sendPhotoBlob multipart trong Worker: cần đúng Content-Type boundary (dùng FormData tự set). Test thật với Telegram API.
- Đổi return openai.ts đụng caller — chỉ 1 caller (/img), an toàn.
- **Mitigation:** test từng lệnh qua `wrangler dev` trước deploy; không có staging.

## Security Considerations
- `assertEnv` KHÔNG log giá trị secret, chỉ tên biến thiếu.
- Q#4: nếu repo public, `ALLOWED_CHAT_IDS`/KV id trong wrangler.toml nên chuyển secret (xử lý ở P4 nếu xác nhận public).

## Next Steps
- Mở khoá P4 (refactor cấu trúc bot) — send layer + http layer đã chuẩn hoá, handlers tách sẽ dùng lại.
- Chờ Q#2 (gpt-image-1) trước finalize step 3-4; Q#6 (fallback OpenAI) nếu muốn implement thay vì xoá dead config.
