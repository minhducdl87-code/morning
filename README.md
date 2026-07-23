# 🐟 Cá Mặn Đau Lưng

> **Tin cho người 3x · Sáng 9h · Cập nhật tối 22h**

Hệ thống bản tin tự động hàng ngày (Morning Digest) + chatbot Telegram thông minh, dành cho đối tượng người 30-40 tuổi Việt Nam. Chạy 100% serverless trên GitHub Actions + Cloudflare.

## Sơ đồ kiến trúc

```
┌─────────────────────────────────────────────────────────────┐
│                     GitHub Actions (cron)                   │
│ 9h sáng (morning) | 22h tối (evening) | CN (weekly) | ngày 1 (tháng) │
└──────────────────────┬──────────────────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
    ┌────────────┐ ┌─────────┐ ┌──────────────┐
    │ Fetch web  │ │ Gemini  │ │ Validate &   │
    │ (Jina +    │→│ 2.5     │→│ Dedup        │
    │  GitHub)   │ │ flash   │ │ (Jaccard 55%)│
    └────────────┘ └─────────┘ └──────────────┘
        ↓              ↓              ↓
    config.json   Topic-agnostic  URL HEAD-check
    (6 topics)                     (ThreadPool)
                       │
                       ▼
                  ┌──────────────┐
                  │ cards.json   │  (rolling 30 ngày)
                  │ weekly.json  │
                  │ monthly.json │
                  └──────────────┘
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
    ┌─────────┐  ┌──────────┐  ┌──────────────┐
    │Telegram │  │ Web site │  │ Chatbot      │
    │ Notify  │  │(Cloudflare│ │ (@caman_bot) │
    │ (9h+10h)│  │ Pages)   │ │ Cloudflare   │
    └─────────┘  └──────────┘  │ Worker KV    │
                                └──────────────┘
```

## Thành phần chính

### 1. **Pipeline sinh bản tin** (Python)
- **Config-driven**: `config.json` định nghĩa 6 topics (tech, finance, entertainment, gaming, Việt Nam, lifestyle), mỗi topic có search queries, RSS feeds, instruction cho LLM, min/max items.
- **Fetch**: `jina_fetch.py` (Jina Search API) + `rss_fetch.py` (RSS/Atom nguồn VN).
- **Generate**: `generate_card.py` gọi Gemini 2.5 flash → parse JSON → HEAD-check URL → dedup Jaccard 55% → ghi `cards.json` (rolling 30 ngày).
- **Rollup**: `generate_weekly.py` (Chủ Nhật) + `generate_monthly.py` (ngày 1 tháng) → tổng hợp từ `cards.json` → ghi `weekly.json` / `monthly.json`.
- **Chống bịa**: Gemini chỉ dùng URL từ dữ liệu đã fetch; sau đó HEAD-check loại link chết; tin không URL sống bị drop.
- **Notify**: `notify-telegram.py` đẩy Telegram lúc 9h (morning, digest đầy đủ) + 22h (evening, chỉ tin mới thêm buổi tối).
- **Cron backup kép**: GitHub Actions cron (nguồn chính) + Cloudflare Worker cron (`bot/src/dispatch.ts`, Kiểu A — wake-up call dự phòng, dispatch `workflow_dispatch` tới `morning.yml`).

### 2. **Chatbot "Caman"** (Cloudflare Worker + TypeScript)
- **Repo**: `bot/` folder — chi tiết xem `bot/README.md`.
- **Commands**: `/start` `/help` `/digest` `/topic` `/week` `/month` `/deep` (GPT-4o) `/img` (image gen) `/clear` + voice (STT) + URL summarize.
- **LLM**: Gemini 2.5 flash (chat + RAG), OpenAI gpt-4o (`/deep`), gpt-image-1 (`/img`), whisper-1 (voice).
- **State**: Cloudflare KV — memory 6 turns (TTL 30 min), rate-limit 60 msg/giờ.
- **Private**: whitelist 2 chat IDs (Anh + Anh Lê).

## Cấu trúc thư mục

| File/Thư mục | Mô tả |
|---|---|
| `config.json` | Topic config (6 topics: enabled, data_source, output_field, emoji, section_label, min/max_items, search_queries, rss_feeds, prompt_instruction, schema) |
| `generate_card.py` | Orchestrator daily: fetch context → Gemini → parse → validate → dedup → write cards.json |
| `generate_weekly.py` | Tổng hợp 7 daily cards → Gemini → write weekly.json (Chủ Nhật) |
| `generate_monthly.py` | Tổng hợp toàn tháng → write monthly.json (ngày 1 tháng, support backfill) |
| `jina_fetch.py` | Fetch data qua Jina Search API + GitHub Search API (dispatcher `fetch_topic_context`) |
| `rss_fetch.py` | Fetch RSS/Atom feed (vnexpress, cafef, tinhte, tuoitre, kenh14, thanhnien, ...) — lọc bài cũ >14 ngày (pubDate), đưa pubDate vào context LLM |
| `digest_utils.py` | Utilities: normalize_title, Jaccard dedup (threshold 0.55), DEDUP_DAYS=7, batch HEAD-check URLs (ThreadPool 8), validate_news_items, URL blacklist |
| `notify-telegram.py` | Push Telegram: lúc 9h (daily digest) + 10h (recap 3 tin top) |
| `bot/` | Cloudflare Worker (TypeScript) — webhook, RAG, commands, LLM integration, KV state |
| `index.html` | Trang web tĩnh (Cloudflare Pages) hiển thị latest digest |
| `_headers` | HTTP headers cho CF Pages |
| `cards.json` | Rolling 30 ngày daily cards — data source cho bot + web |
| `weekly.json` | Tổng kết tuần (12 tuần gần nhất) |
| `monthly.json` | Tổng kết tháng |
| `.github/workflows/` | CI/CD pipelines (morning.yml, deploy-bot.yml, deploy-cloudflare-pages.yml) |

## Cách chạy local

### Yêu cầu
- Python 3.11+
- Gemini API key: `GEMINI_API_KEY`
- Jina API key (tùy chọn): `JINA_API_KEY`
- Telegram bot token (tùy chọn): `TELEGRAM_BOT_TOKEN`

### Setup & chạy

```bash
# Clone repo
git clone <repo> && cd Morning

# Install deps (nếu cần)
pip install google-genai

# Set env vars (hoặc .env file)
export GEMINI_API_KEY=your_key
export JINA_API_KEY=your_key
export TELEGRAM_BOT_TOKEN=your_token  # optional

# Chạy daily digest
python generate_card.py

# Chạy weekly (Sunday)
python generate_weekly.py

# Chạy monthly (1st of month)
python generate_monthly.py

# Notify Telegram
python notify-telegram.py
```

### Local web dev & UI tests

Vite and Playwright are development dependencies. Use `--include=dev` so setup also works when the shell or CI environment has `NODE_ENV=production`.

```bash
# Install the locked dependency tree, including dev dependencies
npm ci --include=dev

# Install the local Playwright browser used by UI tests
npx playwright install chromium

# Start Vite at http://localhost:5180
npm run dev

# Build the production bundle
npm run build

# Run UI tests against the Vite dev server
npm run test:ui

# Build, serve, and smoke-test the production bundle
npm run test:dist
```

Run `npm run test:ui` while developing responsive behavior. Before handoff or deployment, run `npm run test:dist` to validate the production output rather than only the dev server.

### Local bot dev (Cloudflare Worker)

Xem chi tiết tại `bot/README.md` (wrangler dev, secret setup, etc).

## Lịch cron & CI/CD

| Trigger | Schedule (Giờ VN) | Công việc | File |
|---|---|---|---|
| Morning | 9:00 AM | Sinh card mới cho hôm nay + push Telegram (digest đầy đủ) | `generate_card.py` (RUN_MODE=morning) + `notify-telegram.py` |
| Evening | 22:00 PM | Bổ sung tin mới vào card hôm nay (`addedEvening`) + push Telegram (chỉ tin mới) | `generate_card.py` (RUN_MODE=evening) + `notify-telegram.py` |
| Weekly | Chủ Nhật 9:00 AM | Tổng kết tuần | `generate_weekly.py` + push `weekly.json` |
| Monthly | 1st 9:00 AM | Tổng kết tháng | `generate_monthly.py` + push `monthly.json` |
| Manual | On demand (workflow_dispatch) | `run_mode=morning\|evening` / `run_weekly=true` / `run_monthly=true` / `backfill_month=YYYY-MM` | — |
| Cron backup | 9h + 22h VN | Cloudflare Worker cron gọi lại `workflow_dispatch` (Kiểu A, dự phòng nếu GitHub cron trễ) | `bot/src/dispatch.ts` |

## Workflows & Deploy

**`.github/workflows/morning.yml`** — Orchestrate daily/weekly/monthly generation + Telegram notify + auto-push to main

**`.github/workflows/deploy-bot.yml`** — Auto-deploy Cloudflare Worker khi `bot/**` thay đổi
- Đòi hỏi: `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`
- Tự đăng Telegram webhook + sync secrets

**`.github/workflows/deploy-cloudflare-pages.yml`** — Auto-deploy site (index.html + _headers) mỗi push main

## Thêm topic mới

1. Mở `config.json`
2. Thêm key mới dưới `topics` (copy template từ topic hiện có)
3. Set: `enabled`, `data_source`, `output_field`, `emoji`, `section_label`, `min_items`, `max_items`, `search_queries[]`, `rss_feeds[]`, `prompt_instruction`, `schema`
4. Gemini + bot sẽ tự handle (topic-agnostic design)

**Ví dụ:**
```json
"tech_news": {
  "enabled": true,
  "data_source": "jina",
  "output_field": "tech",
  "emoji": "📡",
  "section_label": "Tin Công Nghệ",
  "min_items": 2,
  "max_items": 4,
  "search_queries": ["tin công nghệ {month_year}", "..."],
  "rss_feeds": ["https://..."],
  "prompt_instruction": "...",
  "schema": "{...}"
}
```

## Tech Stack

- **Language**: Python 3.11 (pipeline) + TypeScript (bot)
- **LLM**: Google Gemini 2.5 flash, OpenAI GPT-4o/gpt-image-1/whisper-1
- **Search**: Jina Search API, GitHub Search API, RSS
- **Infrastructure**: GitHub Actions (CI/CD), Cloudflare Workers (bot), Cloudflare Pages (web)
- **State**: Cloudflare KV (bot memory, rate limit)
- **APIs**: Telegram Bot API, Google Gemini API, OpenAI API

## Chỉ số hiệu năng

| Metric | Value |
|---|---|
| Giá tháng (thực tế, 2 user) | ~$0.20 |
| Dedup window | 7 ngày |
| Jaccard threshold | 0.55 (55% content-word overlap) |
| Rate limit (bot) | 60 msg/giờ per user |
| Memory TTL (bot) | 30 phút (6 turns) |
| URL HEAD-check timeout | 5 giây |
| URL HEAD-check workers | 8 threads |
| Rolling card history | 30 ngày |
| Rolling weekly history | 12 tuần |
| Bot chat ID whitelist | 2 |

## Giám sát & troubleshooting

- **GitHub Actions**: Kiểm tra `.github/workflows/` logs nếu workflow fail
- **Telegram**: `notify-telegram.py` log + `TELEGRAM_BOT_TOKEN` secret
- **Bot**: Xem `bot/README.md` — local dev via `wrangler dev`, curl test webhook
- **URL validation**: `digest_utils.py` log "dropped news (dead URL)" khi HEAD-check fail
- **Dedup**: Log "dedup window" + recent titles trích xuất từ `DEDUP_DAYS`

## Liên hệ & License

Dự án: 🐟 Cá Mặn Đau Lưng  
Tác giả: Anh  
License: (xác định sau)
