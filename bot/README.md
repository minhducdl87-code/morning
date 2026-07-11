# 🐟 Caman — @caman_bot

AI chatbot cho Cá Mặn Đau Lưng. Cloudflare Worker + Gemini + OpenAI.

Private bot (whitelist chat IDs): 655323886, 782194719.

## Features

| Command | Handler | Model |
|---|---|---|
| Free text | Chat + RAG over 30-day digest | Gemini 2.5 flash |
| `/start` `/help` | Menu | — |
| `/digest` | Latest daily card | — |
| `/topic <name>` | Filter 7 days by topic | — |
| `/week` | Latest weekly card | — |
| `/month` | Latest monthly card | — |
| `/deep <question>` | Hard question | OpenAI gpt-4o |
| `/img <prompt>` | Image gen | OpenAI gpt-image-1 |
| `/clear` | Wipe history | — |
| Voice message | STT → chat | OpenAI whisper-1 |
| Bare URL | Fetch + summarize | Jina Reader + Gemini |

Rate limit: 60 msg/hour/user (KV counter).
Memory: last 6 turns, 30 min TTL.

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

Copy the `id` output → paste vào `wrangler.toml` field `id`.

### 4. Set secrets

```bash
npx wrangler secret put TELEGRAM_BOT_TOKEN
npx wrangler secret put TELEGRAM_WEBHOOK_SECRET   # any random string, e.g. openssl rand -hex 16
npx wrangler secret put GEMINI_API_KEY
npx wrangler secret put OPENAI_API_KEY
npx wrangler secret put JINA_API_KEY              # optional, only if you have paid Jina
```

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

## Auto-deploy on push

`.github/workflows/deploy-bot.yml` triggers wrangler deploy on push to `main` when `bot/**` files change. Set repo secrets:
- `CLOUDFLARE_API_TOKEN`
- `CLOUDFLARE_ACCOUNT_ID`

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
├── wrangler.toml          # Worker config + KV binding + env vars
├── package.json
├── tsconfig.json
├── README.md              # this file
└── src/
    ├── index.ts           # entry: webhook handler + routing
    ├── types.ts           # Env + DigestData interfaces
    ├── access.ts          # whitelist gate
    ├── telegram.ts        # Telegram API wrapper
    ├── digest.ts          # fetch cards/weekly/monthly from GH Pages
    ├── rag.ts             # RAG: extract top-k relevant items
    ├── memory.ts          # KV history + rate limit
    ├── url-summary.ts     # Jina Reader → LLM summary
    ├── commands.ts        # slash command handlers
    └── llm/
        ├── persona.ts     # system prompt (Cá Mặn persona)
        ├── gemini.ts      # Gemini 2.5 flash chat
        └── openai.ts      # OpenAI chat + image + whisper
```
