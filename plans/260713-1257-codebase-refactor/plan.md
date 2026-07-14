---
title: "Refactor codebase Cá Mặn Đau Lưng (pipeline Python + bot Caman TS)"
description: "Behavior-preserving refactor: dọn nợ kỹ thuật, rút module chung, fix bug bot, thêm test cho pure functions."
status: pending
priority: P2
effort: ~20-26h
branch: main
tags: [refactor, python, typescript, telegram-bot, cleanup]
created: 2026-07-13
---

# Refactor Plan — Cá Mặn Đau Lưng

Nguồn: `plans/reports/reviewer-python-260713-1257-codebase-refactor.md` + `reviewer-bot-260713-1257-codebase-refactor.md`.

## Mục tiêu
Trả nợ kỹ thuật cả 2 hệ (pipeline Python sinh digest + bot Telegram Caman TS) mà **KHÔNG đổi hành vi hiện tại**. Fix 2 bug bot thật (/img fail, message >4096 bị nuốt), rút logic lặp thành module chung, dọn dead code, đặt nền test cho pure functions.

## Nguyên tắc
- **YAGNI / KISS / DRY** — không thêm tính năng mới; chỉ gom lặp + tách concern.
- **Behavior-preserving** — mỗi phase phải verify output không đổi (chạy generator local; curl webhook bot).
- **Mỗi file < 200 LOC** (rule dự án). File import Python giữ snake_case (ràng buộc import).
- **DO NOT** tạo file "enhanced" song song — sửa trực tiếp file gốc.
- Không commit/push (do người dùng quyết định).

## Phases

| # | Phase | Scope | Effort | Rủi ro | Phụ thuộc |
|---|-------|-------|--------|--------|-----------|
| 1 | [Quick wins & dọn rác](phase-01-quick-wins-cleanup.md) | Python + web dead code, crash guard, config gap | ~3h (quick) | Thấp | — |
| 2 | [Refactor pipeline Python](phase-02-refactor-python-pipeline.md) | Tách generate_card.py, gemini-client/json-extract/tz util dùng chung | ~6h (lớn) | Trung | P1 |
| 3 | [Bot bug fixes ưu tiên](phase-03-bot-bug-fixes.md) | H1 /img multipart, H2 split 4096, H3 fetch timeout, M6 assertEnv, M7 báo lỗi | ~4h (quick+bug) | Trung | — |
| 4 | [Refactor cấu trúc bot](phase-04-refactor-bot-structure.md) | Tách index.ts→router+handlers/, telegram-types.ts, gom loadDigest | ~5h (lớn) | Trung | P3 |
| 5 | [Frontend split](phase-05-frontend-split.md) | Tách CSS→styles.css, chia digest.js, bỏ giờ hardcode | ~3h | Thấp | — |
| 6 | [Test coverage pure functions](phase-06-test-coverage.md) | pytest (dedup/url-check/json-extract) + vitest (rag/split/types) | ~5h | Thấp | P2, P4 |

## Thứ tự đề xuất
P1 → P2 (Python xong). P3 → P4 (bot xong). P5 độc lập (bất kỳ lúc nào). P6 cuối (test code đã ổn định). P1/P3/P5 có thể chạy song song (khác vùng file).

## Rủi ro tổng
- Refactor Python (P2) đổi cấu trúc import → chạy `generate_card.py` + `generate_weekly.py` local với env giả, diff JSON output trước/sau.
- Bot deploy qua Cloudflare Worker → không có staging; test bằng `wrangler dev` + curl webhook payload mẫu trước khi deploy.
- Không có test framework sẵn (cả 2 hệ) → P6 phải setup pytest/vitest từ đầu (đưa vào scope).
- CI workflows (`morning.yml`, `deploy-bot.yml`, `deploy-cloudflare-pages.yml`) tham chiếu tên file/entry — nếu đổi tên file phải cập nhật workflow tương ứng.

## Câu hỏi chưa giải đáp (cần Anh quyết trước khi làm phase liên quan)
1. **Monthly có cần LLM summarise?** Docstring nói có, code không có (M1). → Nếu không: sửa docstring thuần aggregate (P1). Nếu có: thành feature mới, ngoài scope refactor.
2. **gpt-image-1 giữ hay đổi model?** Ảnh hưởng cách fix H1 (multipart b64 vs đổi model trả URL) — P3.
3. **config.claude-original.json** xoá hẳn hay chuyển `docs/`? (git đã giữ history) — P1.
4. **Repo public hay private?** Nếu public → `ALLOWED_CHAT_IDS`/KV id hardcode trong wrangler.toml nên chuyển secret — P3/P4.
5. **Priority "Top 3" Telegram** có quan trọng? Nếu có → đưa `priority` vào config.json (M5); nếu không → bỏ PRIORITY_TAGS. (Để P2/ngoài scope tuỳ quyết.)
6. **Fallback Gemini→OpenAI** (OPENAI_CHAT_MODEL dead config M5-bot) implement hay xoá var? — P3/P4.
7. **Mô tả ảnh (msg.photo)** implement Gemini vision hay gỡ khỏi menu/README? (M4-bot) — mặc định gỡ (YAGNI) trong P1/P3.
8. Frontend split chấp nhận nhiều `<script>`/`<link>` (no bundler)? — mặc định có, P5.
