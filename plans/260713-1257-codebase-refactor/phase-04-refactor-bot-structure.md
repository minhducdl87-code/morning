# Phase 04 — Refactor Cấu Trúc Bot

## Context Links
- Report Bot: `plans/reports/reviewer-bot-260713-1257-codebase-refactor.md` (M1, M2, M3, R1, R2, L5, L6, L7)
- Phụ thuộc: **Phase 03** (http.ts + send layer đã có).

## Overview
- **Priority:** P2 (refactor lớn)
- **Status:** pending
- **Effort:** ~5h — Refactor lớn
- Tách `handleUpdate` (~130 dòng, 5 concern) thành router + handlers/; thêm telegram-types.ts bỏ `any`; gom `loadDigest` lặp 6 lần.

## Key Insights
- `handleUpdate` trộn: parse msg → voice STT → command switch → URL summary → free-text RAG (M1). index.ts đang 177 dòng.
- `update: any` xuyên suốt entry (M2) — nghịch lý với `strict` bật.
- `loadDigest(env.SITE_BASE_URL)` lặp 6 lần trong switch (M3) → bảng dispatch với `needsDigest` flag.

## Requirements
- Functional: mọi lệnh/nhánh hành xử **y hệt** trước (voice, /digest /week /month /help /clear /start, URL summary, RAG).
- Non-functional: index.ts mỏng ~40 dòng; mỗi file < 200 LOC; `update: TgUpdate` không còn `any` ở entry; `tsc` strict pass.

## Related Code Files
**Tạo (R1/R2):**
- `bot/src/telegram-types.ts` — `TgUpdate, TgMessage, TgChat, TgUser, TgVoice, TgPhotoSize`; type guard `isMessageUpdate`.
- `bot/src/router.ts` — `handleUpdate`: gate → rate → normalize msg → dispatch.
- `bot/src/handlers/voice-handler.ts` — STT flow.
- `bot/src/handlers/command-router.ts` — bảng dispatch `{ '/digest': fn, ... }` + `needsDigest` flag → load digest 1 lần (M3).
- `bot/src/handlers/url-handler.ts` — URL summary shortcut.
- `bot/src/handlers/chat-handler.ts` — free-text RAG + memory.

**Sửa:**
- `bot/src/index.ts` → chỉ `fetch()` webhook + verify secret + `waitUntil` (~40 dòng); gọi `router.handleUpdate(update as TgUpdate, env)`.
- `bot/src/memory.ts` — `appendHistory` nhận `history` optional để bỏ KV read thừa (L6).
- `bot/src/commands.ts` — dùng type mới nếu cần; (tuỳ chọn) gom magic numbers thành const (L5).

## Implementation Steps
1. Viết `telegram-types.ts` từ shape thực tế đang truy cập (chat.id, from.id, text, voice, photo…).
2. Tách 5 concern thành handlers/; mỗi handler nhận `(msg: TgMessage, env, deps)` rõ ràng.
3. `command-router.ts`: map lệnh→handler; nhóm lệnh `needsDigest` load digest 1 lần truyền vào.
4. `router.ts`: gate whitelist → rate limit → normalize → dispatch (giữ đúng thứ tự index.ts hiện tại).
5. Rút `index.ts` còn webhook shell; `update: any`→`TgUpdate` qua parse + guard.
6. `appendHistory(userId, msg, reply, history?)` — free-text path truyền history sẵn (L6).
7. (Tuỳ chọn L7) chỉ rate-limit lệnh gọi LLM — CHỜ xác nhận vì đổi hành vi rate-limit (không thuần refactor).
8. `tsc --noEmit` pass; diff hành vi qua `wrangler dev`.

## Todo
- [x] telegram-types.ts + guard
- [x] handlers/ (voice, command-router, url, chat) — cộng thêm photo-handler (Q7 feature)
- [x] router.ts orchestrate đúng thứ tự cũ
- [x] index.ts mỏng ~40 dòng (43), bỏ `any`
- [x] command-router load digest 1 lần
- [x] appendHistory nhận history (L6)
- [x] tsc strict pass; mỗi file < 200 LOC

## Success Criteria
- `wrangler dev` + curl từng payload (voice, mỗi command, URL, free-text) → output giống baseline P3.
- `grep ': any' bot/src/index.ts` → 0 (hoặc chỉ chỗ không tránh được, có chú thích).
- `wc -l bot/src/index.ts` ≤ ~50.
- Không lệnh nào gọi `loadDigest` > 1 lần/lượt.

## Risk
- Trung. Dễ đổi thứ tự gate/rate/dispatch khi tách → BẮT BUỘC giữ nguyên trình tự (whitelist → rate → command). Viết checklist thứ tự trước khi tách.
- **Mitigation:** so sánh phản hồi từng nhánh trước/sau qua wrangler dev với payload cố định.

## Security Considerations
- Giữ nguyên whitelist (access.ts) + webhook secret verify + rate limit — không được nới trong lúc tách.
- Q#4: nếu repo public → chuyển `ALLOWED_CHAT_IDS` sang secret (wrangler secret) thay vì wrangler.toml.
- Q#5: nếu tương lai hỗ trợ nhóm/channel → router thiết kế nhận nhiều chat; hiện giữ single-chat (YAGNI).

## Next Steps
- Mở khoá P6 (test): handlers/rag/split dễ unit-test sau khi tách.
- Nếu đổi tên/entry file → cập nhật `deploy-bot.yml` (xác nhận entry `src/index.ts` không đổi → workflow OK).
