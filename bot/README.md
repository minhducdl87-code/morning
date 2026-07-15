# 🐟 Caman — @caman_bot

AI chatbot cho Cá Mặn Đau Lưng. Cloudflare Worker + Gemini + OpenAI.

Private bot (whitelist chat IDs): 655323886, 782194719.

## Features

| Command | Handler | Model |
|---|---|---|
| Free text | Chat + RAG over 30-day digest (Gemini, falls back to OpenAI if Gemini fails) | Gemini 2.5 flash → OpenAI gpt-4o-mini |
| `/start` `/help` | Menu | — |
| `/digest` | Latest daily card | — |
| `/topic <name>` | Filter 7 days by topic | — |
| `/week` | Latest weekly card | — |
| `/month` | Latest monthly card | — |
| `/deep <question>` | Hard question | OpenAI gpt-4o |
| `/img <prompt>` | Image gen (returns URL; code also handles base64 for gpt-image-1) | OpenAI dall-e-3 |
| `/clear` | Wipe history | — |
| Voice message | STT → chat | OpenAI whisper-1 |
| Photo | Describe/OCR content (caption becomes the question) | Gemini 2.5 flash vision |
| Bare URL | Fetch + summarize | Jina Reader + Gemini |

Rate limit: 60 msg/hour/user (KV counter).
Memory: last 6 turns, 30 min TTL.
Long replies (digest/week/month/RAG/summary) are auto-split at Telegram's 4096-char limit.
All outbound HTTP calls (Gemini/OpenAI/Jina/Telegram) use a timeout so the Worker never hangs.

## Setup (one time)

### 1. Create bot on Telegram

1. Chat với [@BotFather](https://t.me/BotFather) → `/newbot` → username `caman_bot`
2. Copy bot token → dùng bước 4
3. `/setcommands` → paste:
   ```
   start - Bắt đầu
   help - Menu
   digest - Bảng tin hôm nay
   topic - Filter theo chủ đề (tech|finance|...)
   week - Tổng kết tuần
   month - Tổng kết tháng
   deep - Câu hỏi sâu (GPT-4o)
   img - Sinh ảnh
   clear - Xóa lịch sử chat
   ```

### 2. Install wrangler + login

```bash
cd bot
npm install
npx wrangler login
```

### 3. Create KV namespace

```bash
npx wrangler kv namespace create STATE
```

Copy the `id` output. This repo is **public**, so `wrangler.toml` only commits a
`REPLACE_WITH_KV_NAMESPACE_ID` placeholder — do NOT commit the real id.

- **Local dev/deploy**: temporarily paste the real id into `wrangler.toml`
  field `id`, test, then revert (`git checkout -- wrangler.toml`) before
  committing anything else.
- **CI deploy**: set a GitHub repo secret `CF_KV_NAMESPACE_ID` with the real
  id — the workflow substitutes it into `wrangler.toml` at deploy time (see
  `.github/workflows/deploy-bot.yml`).

### 4. Set secrets

```bash
npx wrangler secret put TELEGRAM_BOT_TOKEN
npx wrangler secret put TELEGRAM_WEBHOOK_SECRET   # any random string, e.g. openssl rand -hex 16
npx wrangler secret put GEMINI_API_KEY
npx wrangler secret put OPENAI_API_KEY
npx wrangler secret put ALLOWED_CHAT_IDS          # comma-separated whitelist chat IDs, e.g. "655323886,782194719"
npx wrangler secret put JINA_API_KEY              # optional, only if you have paid Jina
npx wrangler secret put GH_DISPATCH_TOKEN         # optional — see "Cron trigger" section below
```

`ALLOWED_CHAT_IDS` used to live in `wrangler.toml` `[vars]` (safe when the
repo was private). Since the repo is now public, it's a secret instead so
real user chat IDs aren't committed.

### 5. Deploy

```bash
npx wrangler deploy
```

Output: `https://caman-bot.<account>.workers.dev`

### 6. Register Telegram webhook

Replace `<TOKEN>`, `<SECRET>`, and `<WORKER_URL>`:

```bash
curl "https://api.telegram.org/bot<TOKEN>/setWebhook?url=<WORKER_URL>/webhook&secret_token=<SECRET>&drop_pending_updates=true"
```

Verify:
```bash
curl "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"
```

### 7. Test

Message the bot on Telegram:
- `/start` → welcome
- `/digest` → today's card
- "AI có tin gì mới?" → Gemini chat with RAG
- Send a URL → summarize
- Send voice → STT + reply

## Cron trigger (Kiểu A — Worker wakes GitHub Actions)

`wrangler.toml` `[triggers]` schedules the Worker's `scheduled()` handler at
`0 2 * * *` (9h VN, morning) and `0 15 * * *` (22h VN, evening). Instead of
doing the digest generation itself, the Worker just calls
`dispatchWorkflow()` (`src/dispatch.ts`) which POSTs a
`workflow_dispatch` event to `morning.yml` with `inputs.run_mode` set to
`morning`/`evening` accordingly. GitHub Actions' own cron (`.github/workflows/morning.yml`)
stays the primary schedule/source of truth; the Worker cron is a second,
independent wake-up call in case the GitHub Actions cron is delayed —
`generate_card.py`'s own guards (today's-card-exists / eveningDone) make
double-triggering harmless.

Requires secret `GH_DISPATCH_TOKEN` — a GitHub **fine-grained PAT** scoped to
this repo with **Actions: Read and write** permission (Settings → Developer
settings → Fine-grained tokens). Optional: if unset, the cron handler logs an
error and no-ops (webhook/chat path is unaffected — `GH_DISPATCH_TOKEN` is
NOT in `env-guard.ts`'s required keys).

## Auto-deploy on push

`.github/workflows/deploy-bot.yml` triggers wrangler deploy on push to `main` when `bot/**` files change. Set repo secrets:
- `CLOUDFLARE_API_TOKEN`
- `CLOUDFLARE_ACCOUNT_ID`
- `CF_KV_NAMESPACE_ID` — real STATE KV namespace id (injected into `wrangler.toml` placeholder at deploy time)
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`, `GEMINI_API_KEY`, `OPENAI_API_KEY`, `ALLOWED_CHAT_IDS` — synced to the Worker as `wrangler secret`
- `JINA_API_KEY` — optional
- `GH_DISPATCH_TOKEN` — optional, powers the cron → GitHub Actions dispatch above

## Local dev

```bash
cd bot
npx wrangler dev
```

Test via curl:
```bash
curl -X POST http://localhost:8787/webhook \
  -H "X-Telegram-Bot-Api-Secret-Token: <SECRET>" \
  -H "content-type: application/json" \
  -d '{"message":{"chat":{"id":655323886},"from":{"id":655323886},"text":"/start"}}'
```

## Cost (100 users hypothetical)

Actual (Anh + Anh Le): ~$0.20/mo, mostly OpenAI.

## Files

```
bot/
├── wrangler.toml          # Worker config + KV binding (placeholder id) + public env vars
├── package.json
├── tsconfig.json
├── README.md              # this file
└── src/
    ├── index.ts           # entry: webhook shell only (health check, secret verify, JSON parse)
    ├── router.ts           # handleUpdate: gate → rate limit → normalize msg → dispatch
    ├── telegram-types.ts   # Telegram Update/Message/Chat/Voice/PhotoSize types
    ├── types.ts            # Env + DigestData interfaces
    ├── access.ts           # whitelist gate
    ├── env-guard.ts         # assertEnv() — validates required env/secrets at request start
    ├── dispatch.ts           # cron trigger → dispatchWorkflow() POSTs morning.yml workflow_dispatch
    ├── http.ts              # fetchWithTimeout / fetchJson — used by every external call
    ├── binary.ts             # base64 <-> bytes helpers
    ├── telegram.ts          # Telegram API wrapper (sendMessage/sendLongMessage/sendPhotoBlob)
    ├── digest.ts            # fetch cards/weekly/monthly from GH Pages
    ├── rag.ts               # RAG: extract top-k relevant items
    ├── memory.ts            # KV history + rate limit
    ├── url-summary.ts       # Jina Reader → LLM summary
    ├── commands.ts          # slash command handlers
    ├── handlers/
    │   ├── voice-handler.ts     # STT flow
    │   ├── photo-handler.ts     # vision describe/OCR flow
    │   ├── command-router.ts    # slash command dispatch table, loads digest once
    │   ├── url-handler.ts       # bare-URL summary shortcut
    │   └── chat-handler.ts      # free-text RAG + memory + OpenAI fallback
    └── llm/
        ├── persona.ts     # system prompt (Cá Mặn persona)
        ├── gemini.ts      # Gemini 2.5 flash chat + vision
        └── openai.ts      # OpenAI chat + image + whisper
```
