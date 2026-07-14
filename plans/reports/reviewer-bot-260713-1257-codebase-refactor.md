# Review Bot Caman (Telegram / Cloudflare Worker) — Định hướng Refactor

**Ngày:** 2026-07-13
**Phạm vi:** `bot/` (11 file TS, wrangler.toml, tsconfig.json, package.json, README.md)
**Chế độ:** Review-only, không sửa code.
**Tổng LOC (src):** ~600 dòng TS.

---

## 1. Tóm tắt

Codebase nhỏ, gọn, tổ chức module hợp lý (mỗi concern 1 file, đều < 200 dòng — đạt chuẩn CLAUDE.md). Persona/prompt engineering tốt, error handling cơ bản có (try/catch + trả null). `tsconfig` đã bật `strict` + `noImplicitAny` — tốt.

**Nợ kỹ thuật chính:**
- `handleUpdate` (index.ts, ~130 dòng) trộn 5 concern → khó test, khó mở rộng.
- Thiếu type Telegram update → `any` xuyên suốt entry, mất an toàn ngay ở ranh giới dữ liệu vào.
- **2 bug chức năng thật:** `/img` với `gpt-image-1` gần như luôn fail; tính năng "mô tả ảnh" README hứa nhưng không có code.
- Không có message-splitting cho giới hạn 4096 char của Telegram → reply dài bị nuốt im lặng.
- Không có timeout cho bất kỳ fetch nào (LLM/Jina/Telegram).

Không phát hiện lỗ hổng bảo mật nghiêm trọng: whitelist + webhook secret + rate limit đều có. Không thấy log secret.

---

## 2. Findings theo severity

### 🔴 Critical / High

**H1 — `/img` với `gpt-image-1` luôn fail (bug thật).**
`llm/openai.ts:38-54` + `index.ts:138-139`. `gpt-image-1` (đang cấu hình ở `wrangler.toml:21`) **chỉ trả `b64_json`, không hỗ trợ `url`**. Code đi vào nhánh `d.b64_json` → trả `data:image/png;base64,...`. Nhưng `sendPhoto` (`telegram.ts:28-29`) gửi chuỗi này qua field `photo` trong JSON body — Telegram sendPhoto qua JSON chỉ nhận **HTTP URL hoặc file_id**, KHÔNG nhận data URI. ⇒ `/img` luôn báo lỗi hoặc fail.
*Refactor:* upload ảnh b64 qua `multipart/form-data` (blob) tới sendPhoto, hoặc đổi model sang loại trả URL. Cần 1 hàm `sendPhotoBlob`.

**H2 — Không split message theo giới hạn 4096 char Telegram.**
`telegram.ts:18` `sendMessage` không cắt. `/digest`, `/week`, `/month`, RAG reply, URL summary đều có thể > 4096. `call()` trả `null` + `console.error` → user **không nhận được reply**, im lặng. Edge case xảy ra thật với digest nhiều mục.
*Refactor:* thêm `sendLongMessage()` chunk theo 4096 (cắt ở ranh giới dòng), hoặc truncate + "..." an toàn.

**H3 — Fetch không có timeout (toàn bộ).**
`gemini.ts`, `openai.ts`, `url-summary.ts`, `digest.ts`, `telegram.ts` — không dùng `AbortController`. LLM/Jina treo → `handleUpdate` treo trong `waitUntil`, user không nhận phản hồi, tốn CPU-time Worker.
*Refactor:* helper `fetchWithTimeout(url, opts, ms)` dùng chung, ví dụ 20s cho LLM, 10s cho Jina/Telegram.

### 🟠 Medium

**M1 — `handleUpdate` trộn concern (index.ts:48-177).**
Parse msg → voice STT → command switch → URL summary → free-text RAG trong 1 hàm ~130 dòng. Khó unit-test từng nhánh.
*Refactor lớn:* xem mục 3.

**M2 — Thiếu type Telegram update.**
`index.ts:38,48` `update: any`; `msg`, `msg.chat`, `msg.voice`... đều any. Mất autocomplete + không bắt lỗi field sai lúc compile (nghịch lý: `strict` bật nhưng dữ liệu vào là any).
*Refactor:* thêm `telegram-types.ts` (`TgUpdate`, `TgMessage`, `TgChat`, `TgUser`, `TgVoice`, `TgPhotoSize`). Parse `update` thành `TgUpdate`.

**M3 — DRY: `loadDigest(env.SITE_BASE_URL)` lặp 6 lần trong switch (index.ts:112-129).**
Mỗi case digest gọi lại. Dù CF cache 5 phút, vẫn lặp code.
*Refactor:* load 1 lần cho nhóm command cần digest, hoặc bảng dispatch `{cmd: handler}` với `needsDigest` flag.

**M4 — Tính năng "mô tả ảnh" hứa nhưng thiếu.**
`commands.ts:47` (menu /start) + README:18 quảng cáo "Ảnh → em mô tả nội dung", nhưng `index.ts` không có nhánh `msg.photo`. Ảnh không caption → rơi vào "Em chỉ hiểu text/voice" (index.ts:92). Hoặc implement (Gemini vision) hoặc gỡ khỏi menu/README (KISS/YAGNI).

**M5 — Config chết: `OPENAI_CHAT_MODEL` không dùng.**
`types.ts:14` + `wrangler.toml:19` (`gpt-4o-mini`) khai báo nhưng grep không thấy dùng ở đâu. README nhắc "fallback" nhưng không có logic fallback Gemini→OpenAI.
*Refactor:* hoặc implement fallback thật (Gemini null → openaiChat), hoặc xóa var (dead config).

**M6 — Không validate env lúc khởi động.**
Thiếu `GEMINI_API_KEY`/`OPENAI_API_KEY` chỉ lộ ra khi call → trả null → "Em đang lag". Khó chẩn đoán.
*Refactor:* hàm `assertEnv(env)` kiểm biến bắt buộc, log rõ khi thiếu (không log giá trị).

**M7 — `waitUntil` nuốt lỗi, user không được báo.**
`index.ts:43`. Nếu `handleUpdate` throw trước khi kịp sendMessage (vd `checkRateLimit` KV lỗi), user im lặng. Nên bọc try/catch trong `handleUpdate` để gửi fallback "có lỗi, thử lại" cho user.

### 🟡 Low

**L1 — KV rate-limit race (memory.ts:30-37).** Read-modify-write không atomic. 2 message đồng thời cùng đọc count → cùng ghi → đếm hụt. Không critical (chỉ nới nhẹ giới hạn). KV vốn không hỗ trợ atomic increment; chấp nhận được, ghi chú lại.

**L2 — Rate window là sliding, không fixed (memory.ts:35).** Mỗi `put` reset `expirationTtl` = 3600s ⇒ counter chỉ hết hạn 1h sau message CUỐI, không phải message đầu. User chạm limit phải im lặng đủ 1h. Không đúng ngữ nghĩa "60/giờ". Cân nhắc lưu `{count, windowStart}`.

**L3 — `esc()` không escape dấu `"` (telegram.ts:42-44).** Trong context `href="${esc(url)}"` (commands.ts:24, index.ts:155), URL chứa `"` sẽ phá vỡ attribute. URL hợp lệ hiếm khi có, nhưng URL từ digest/user không kiểm soát 100%. Thêm `"`→`&quot;` cho an toàn HTML-attr.

**L4 — Heuristic URL summary mong manh (index.ts:150).** `trimmed.length < foundUrl.length + 20`: "tóm tắt giúp em <url dài>" sẽ KHÔNG trigger summary mà rơi vào RAG chat. Ngưỡng 20 magic. Cân nhắc: có URL + ít chữ khác ⇒ summarize.

**L5 — Magic numbers rải rác.** `slice(0,150)` (rag.ts:75), `slice(0,140)` (commands.ts:23), `slice(0,3)`, `MAX_CONTENT=6000`, `topK` khác nhau (index dùng 10, cmdDeep 15). Gom thành const có tên.

**L6 — `appendHistory` đọc lại KV thừa (memory.ts:16-17).** Trong free-text path (index.ts:164) đã có `history` nhưng `appendHistory` gọi `getHistory` lần nữa. 1 KV read thừa/lượt. Cho phép truyền history vào.

**L7 — Rate limit tính cả `/help`, `/clear`, `/start`.** Check trước khi phân loại command (index.ts:65). Lệnh nhẹ vẫn tốn quota. Cân nhắc chỉ rate-limit lệnh gọi LLM.

---

## 3. Cơ hội refactor lớn (nhóm theo module)

### R1 — Tách `index.ts` → router + handlers
```
src/
├── index.ts              # chỉ: fetch() webhook, verify secret, waitUntil (mỏng ~40 dòng)
├── router.ts             # handleUpdate: gate → rate → normalize msg → dispatch
├── telegram-types.ts     # TgUpdate, TgMessage, TgChat, TgUser, TgVoice...
└── handlers/
    ├── voice-handler.ts     # STT flow
    ├── command-router.ts    # bảng dispatch { '/digest': fn, ... }, xử lý loadDigest 1 lần
    ├── url-handler.ts        # URL summary shortcut
    └── chat-handler.ts       # free-text RAG + memory
```
Lợi: mỗi nhánh test độc lập, `command-router` dùng bảng thay switch → xóa lặp `loadDigest`.

### R2 — `telegram-types.ts` + parse an toàn
Định nghĩa interface Telegram, đổi `update: any` → `update: TgUpdate`. Xóa toàn bộ `any` ở entry. Có thể thêm type guard `isMessageUpdate`.

### R3 — HTTP layer dùng chung
`http.ts`: `fetchWithTimeout()` + `fetchJson()` (đang lặp ở digest.ts) + xử lý retry nhẹ (1 lần) cho LLM 5xx. Dùng lại ở mọi module fetch.

### R4 — Telegram send layer chuẩn hóa
Thêm `sendLongMessage` (chunk 4096) và `sendPhotoBlob` (multipart cho b64). Chuyển reply dài sang `sendLongMessage`.

---

## 4. Quick wins vs Refactor lớn

| Quick wins (ít rủi ro, làm ngay) | Refactor lớn (cần plan) |
|---|---|
| H2: thêm `sendLongMessage` chunk 4096 | R1: tách index.ts → router + handlers/ |
| H3: `fetchWithTimeout` helper dùng chung | R2: telegram-types.ts, bỏ `any` |
| M5: xóa `OPENAI_CHAT_MODEL` (hoặc nối fallback) | R3: gom HTTP layer + retry |
| M6: `assertEnv()` validate biến bắt buộc | H1: sửa `/img` (multipart sendPhoto b64) |
| M7: try/catch trong handleUpdate báo lỗi user | M1/M3: bảng dispatch command, load digest 1 lần |
| L3: escape `"` trong `esc()` | M4: implement/gỡ mô tả ảnh |
| L5: gom magic numbers thành const | |

---

## 5. Điểm tốt (giữ nguyên)

- Module hóa sạch, mọi file < 200 dòng (đúng chuẩn CLAUDE.md).
- `strict` + `noImplicitAny` bật sẵn.
- Bảo mật cơ bản đủ: whitelist (access.ts), webhook secret (index.ts:33-36), rate limit.
- Error handling nhất quán: mọi LLM/fetch bọc try/catch, trả `null`, có fallback message thân thiện.
- RAG có dedup theo URL + stopwords VN, fallback "no query → recent".
- Persona/prompt có rule cứng chống bịa tin/URL — tốt.
- Không log secret; API key Gemini nằm trong query nhưng không bị console.error ra ngoài.

---

## 6. Câu hỏi chưa giải đáp

1. **`gpt-image-1`** — có chủ đích không, hay từng dùng model trả URL? (ảnh hưởng cách sửa H1)
2. **Fallback Gemini→OpenAI** — có định implement (giải thích `OPENAI_CHAT_MODEL`) hay bỏ hẳn?
3. **Mô tả ảnh (msg.photo)** — muốn implement bằng Gemini vision hay gỡ khỏi menu/README?
4. `ALLOWED_CHAT_IDS` + KV `id` hardcode trong `wrangler.toml` (commit vào git) — chấp nhận được với repo private, nhưng nếu repo public thì nên chuyển ALLOWED_CHAT_IDS sang secret. Repo này public hay private?
5. Có cần hỗ trợ nhóm/channel (nhiều chat) trong tương lai không? Ảnh hưởng thiết kế router.
