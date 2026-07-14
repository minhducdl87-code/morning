# 🐟 Cá Mặn Đau Lưng — Product Development Requirements (PDR)

**Document version**: 1.0  
**Last updated**: 2026-07-13  
**Status**: Active

---

## 1. Tổng quan sản phẩm

### Vision
Tạo hệ thống bản tin tự động hàng ngày (Morning Digest) + chatbot thông minh dành cho đối tượng người 30-40 tuổi Việt Nam, giúp họ cập nhật tin tức quan trọng theo sở thích, mà không cần phải dò tìm trên 10 website khác nhau. Tin tức được cấp chế bởi AI (Gemini), lọc chống bịa URL, dedup thông minh, và được đẩy qua Telegram mỗi sáng 9 giờ.

### Problem Statement
- **Người dùng 30-40 tuổi VN** bận rộn, không có thời gian đọc nhiều nguồn tin
- **Thông tin quá tải**: phải theo dõi multiple sites (vnexpress, genk, cafef, ...), RSS feeds không được đồng bộ
- **Fake news / tin bịa**: bình luận AI (ChatGPT, Gemini) có thể hallucinate URL, dẫn đến click vào link chết hoặc gây mất thời gian
- **Thiếu tính cá nhân hóa**: một người quan tâm tech + finance, người khác chỉ muốn entertainment + Việt Nam news

### User Persona
- **Tên**: Anh/Chị 30-40 tuổi, thường trú Hà Nội/TP HCM
- **Nghề nghiệp**: IT, kinh doanh, marketing, finance
- **Hành vi**: dùng Telegram hàng ngày, thích nhận thông tin sáng sớm trước khi vào làm
- **Mục tiêu**: cập nhật tin tức nhanh (5-10 phút), đỡ phải scan 6-7 website, có link thật có thể click xem thêm
- **Pain point**: tin lá cải, link chết, thông tin giả

### Value Proposition
- **Mỗi sáng 9h**: nhận 1 bản tin digest (1 message) với 6 chủ đề, tổng ~20 tin được lựa chọn thông minh
- **Không fake**: mỗi tin phải có URL sống (HEAD-check), Gemini chỉ dùng dữ liệu đã fetch, không bịa
- **Dedup thông minh**: không lặp tin cũ trong vòng 7 ngày, dù viết lại bằng cách khác (Jaccard 55%)
- **Chatbot riêng**: hỏi thêm về bất kỳ tin nào, lấy tin cũ theo topic, summary URL, sinh ảnh, dùng GPT-4o cho câu hỏi sâu
- **Chi phí thấp**: ~$0.20/tháng (chỉ Gemini + OpenAI), serverless (0 server ops)

---

## 2. Mục tiêu & phạm vi

### Functional Goals (FG)
1. **FG1**: Sinh daily digest tự động lúc 9h sáng, chứa 6 topic: tech, finance, entertainment, gaming, Việt Nam, lifestyle
2. **FG2**: Mỗi topic có 2-5 tin (tuỳ config), full URL + description + tag
3. **FG3**: Tổng hợp tuần (Chủ Nhật), tổng hợp tháng (ngày 1) từ daily cards
4. **FG4**: Chống fake URL: HEAD-check mỗi URL, drop nếu chết hoặc blacklist
5. **FG5**: Dedup: Jaccard token 55% trong cửa sổ 7 ngày, normalize emoji/dấu câu
6. **FG6**: Chatbot Telegram (@caman_bot) với 9 command + voice + URL summary
7. **FG7**: Bot RAG: tìm tin liên quan từ 30 ngày digest dựa trên câu hỏi user
8. **FG8**: Rate limit bot: 60 msg/giờ per user, memory 6 turns (30 min TTL)
9. **FG9**: Deploy tự động: push code → GH Actions sinh digest → push cards.json; push bot/ → auto-deploy Worker

### Non-functional Goals (NFG)
1. **NFG1**: Chi phí ≤ $0.50/tháng (thực tế ~$0.20)
2. **NFG2**: Latency: digest sinh < 5 phút, Telegram push < 1 phút
3. **NFG3**: Uptime: 99%+ (GitHub Actions + Cloudflare SLA)
4. **NFG4**: Scalability: serverless, không có server riêng để maintain
5. **NFG5**: Security: bot whitelist 2 chat ID, không lưu credential trên repo
6. **NFG6**: Maintainability: config-driven topics, topic-agnostic code (thêm topic chỉ sửa config.json)

### Out of Scope (không làm lúc này)
- Không phát triển mobile app (chỉ Telegram + web)
- Không có user auth (bot riêng tư, whitelist cứng)
- Không lưu user preference profile (stateless, config cứng)
- Không push desktop notification (chỉ Telegram)
- Không có analytics/tracking (privacy-first)

---

## 3. Yêu cầu chức năng (Functional Requirements)

### FR1: Pipeline sinh bản tin hàng ngày
**Trigger**: Lúc 9h sáng VN (cron `0 2 * * *` UTC = 9h Ho Chi Minh)

**Input**:
- `config.json` với 6 topics, mỗi topic có:
  - `search_queries[]`: 3-4 query để Jina Search (hỗ trợ `{month_year}` placeholder)
  - `rss_feeds[]`: URL danh sách RSS/Atom feed
  - `prompt_instruction`: hướng dẫn cho Gemini
  - `min_items`, `max_items`: số tin mong muốn
  - `schema`: JSON schema trả về cho mỗi tin

**Process**:
1. Đọc config → lấy topics enabled
2. Gọi `jina_fetch.py`: query Jina Search API + GitHub Search (nếu có) → trả dữ liệu raw
3. Gọi `rss_fetch.py`: fetch RSS/Atom feeds → extract articles
4. Build prompt Gemini với:
   - Dữ liệu tìm kiếm (context)
   - HARD RULE: URL phải từ dữ liệu fetch, không bịa
   - Danh sách tin cũ 7 ngày gần (prevent repeat)
5. Gọi Gemini 2.5 flash → parse JSON response
6. Batch HEAD-check tất cả URL (8 threads, 5s timeout) → loại link chết
7. Drop tin không có URL sống
8. Validate dedup: Jaccard token >= 0.55 = duplicate → drop
9. Write `cards.json` (append, rolling 30 ngày)
10. Log: # topics, # items per topic, # dropped, # dedup, # URL fail

**Output**: `cards.json` với schema:
```json
{
  "date": "2026-07-13",
  "dayLabel": "Chủ Nhật",
  "dateLabel": "13/07/2026",
  "tech": [
    {"title": "emoji + title", "desc": "tiếng Việt max 2 câu", "tag": "launch", "tagLabel": "🚀 LAUNCH", "source": "13/07 · genk.vn", "url": "https://..."}
  ],
  "finance": [...],
  ...
}
```

### FR2: Chống fake URL (điểm thiết kế cốt lõi)
**Rule 1**: Gemini chỉ được dùng URL từ dữ liệu đã fetch (Jina/GitHub/RSS)
- Prompt phải nêu rõ: "URL chỉ từ Dữ liệu tìm kiếm"
- Nếu không chắc URL → set `"url": ""` (empty string, item vẫn hiển thị)
- Tuyệt đối KHÔNG bịa pattern plausible

**Rule 2**: HEAD-check mỗi URL sau khi Gemini generate
- Method: HEAD request → status 2xx/3xx = sống, else = chết
- Timeout: 5 giây
- Fallback: nếu HEAD fail → thử GET với Range header (một số server block HEAD)
- Blacklist: `vertexaisearch.cloud.google.com` (Gemini grounding token expire), `link-ho` (schema leak)
- Parallel: ThreadPool 8 workers

**Rule 3**: Drop tin không có URL sống
- News item PHẢI có URL sống
- Repo item PHẢI match `github.com/owner/repo` pattern + URL sống
- If URL empty → OK (tin vẫn hiển thị), nhưng người dùng không click được

### FR3: Dedup thông minh (Jaccard token, 7 ngày)
**Window**: DEDUP_DAYS = 7 ngày (từ hôm nay tính lùi)

**Algorithm**:
1. `normalize_title(s)`: loại emoji, dấu câu → lower → collapse space
2. `_tokens(s)`: từ normalized → loại stopword VN+EN + từ 1 ký tự
3. Xây `dedup_index`: exact normalized set + token sets list
4. `is_duplicate_title(new_title, exact_norms, tokens_list, threshold=0.55)`:
   - Nếu exact match → duplicate
   - Jaccard = |A ∩ B| / |A ∪ B| ≥ 0.55 → duplicate (bắt paraphrase reorder)

**Output**: drop duplicate title → log "dedup: {title}" → không append vào cards.json

### FR4: Tổng hợp tuần (Weekly Digest)
**Trigger**: Chủ Nhật 9h sáng (cron `0 2 * * 0` UTC)

**Input**: cards.json — extract tất cả tin trong 7 ngày

**Process**:
1. Load all cards → filter 7 ngày gần
2. Compact: mỗi topic-list item → 1 row (date + topic + title + url + source)
3. Build prompt Gemini: "tóm tắt tuần này — top tin mỗi topic"
4. HEAD-check URL → drop chết
5. Write `weekly.json` (rolling 12 tuần)

**Output**: `weekly.json` schema tương tự cards, nhưng với `weekNum` thay vì `date`

### FR5: Tổng hợp tháng (Monthly Digest)
**Trigger**: Ngày 1 tháng 9h sáng (cron `0 2 1 * *` UTC) hoặc manual backfill

**Process**: Tương tự FR4 nhưng 30 ngày, write `monthly.json` (rolling)

**Backfill**: Accept `--backfill YYYY-MM` argument → sinh digest cho tháng cụ thể

### FR6: Notify Telegram
**Trigger**: 
- 9h sáng: push full daily digest (mode: `digest`)
- 10h sáng: push recap 3 tin top (mode: `recap`)

**Process**:
1. Load latest card từ cards.json
2. Format Telegram message (markdown): emoji + topic section + tin + link
3. Gửi via Telegram Bot API
4. Log: message ID, recipient chat IDs, success/fail

### FR7: Chatbot Telegram (@caman_bot)
**Entry**: Cloudflare Worker webhook `/webhook`

**Commands**:
| Command | Handler | LLM | Input | Output |
|---|---|---|---|---|
| `/start` | Menu | — | — | Welcome message + help |
| `/help` | Menu | — | — | Command list |
| `/digest` | Fetch latest | — | — | Today's card |
| `/topic <name>` | Filter | — | tech\|finance\|... | 7-day items của topic |
| `/week` | Fetch latest | — | — | Weekly card |
| `/month` | Fetch latest | — | — | Monthly card |
| Free text | Chat + RAG | Gemini 2.5 flash | "AI có tin gì?" | Chat response + top-3 relevant items |
| `/deep <q>` | Hard Q | OpenAI GPT-4o | "Tác động gì?" | Deep analysis |
| `/img <prompt>` | Image gen | OpenAI gpt-image-1 | "ảnh con mèo" | Generated image URL |
| Voice message | STT | OpenAI whisper-1 | Audio | Transcribe + chat reply |
| Bare URL | Summarize | Jina Reader + Gemini | "https://..." | 1-para summary |

**Details**:
- **RAG**: Fetch digest từ GitHub Pages (cards.json) → BM25 retrieval → top-3 relevant items
- **Memory**: KV store — last 6 turns, TTL 30 min
- **Rate limit**: 60 msg/giờ per user (KV counter)
- **Persona**: System prompt defined in `llm/persona.ts` — "Cá Mặn persona", friendly professional tone

### FR8: Web site (Cloudflare Pages)
**Deploy**: `index.html` + `_headers` → Cloudflare Pages

**Content**: Render latest cards.json → display digest in responsive layout

**Update**: Auto-deploy khi push main (`deploy-cloudflare-pages.yml`)

---

## 4. Yêu cầu phi chức năng (Non-functional Requirements)

### NFR1: Performance
- **Daily digest generation**: < 5 phút (fetch + Gemini + validate + push)
- **Telegram push**: < 1 phút
- **Bot command response**: < 3 giây (cached digest, KV lookup)
- **URL HEAD-check**: parallel 8 threads, 5s timeout per URL

### NFR2: Reliability
- **GitHub Actions**: cron reliable 99%+, retry on fail
- **Cloudflare Worker**: 99.95% uptime SLA
- **Bot**: auto-restart on Telegram webhook fail, queue retry
- **Data integrity**: cards.json commit atomically, never partial write

### NFR3: Cost
- **Target**: ≤ $0.50/mo; actual: ~$0.20/mo (2 users)
- **Cost breakdown**:
  - Gemini API: ~$0.10/mo (50 daily calls @ ~$0.001 per call)
  - OpenAI (gpt-4o + gpt-image-1 + whisper): ~$0.08/mo (occasional)
  - Jina API: free tier (paid tier optional)
  - GitHub Actions: free tier
  - Cloudflare Worker: free tier (≤ 100k req/day)
  - Cloudflare Pages: free
  - Cloudflare KV: free tier (≤ 100k ops/day)

### NFR4: Security
- **Bot whitelist**: hardcode 2 chat IDs, reject unknown users
- **Secrets**: store `GEMINI_API_KEY`, `OPENAI_API_KEY`, `JINA_API_KEY`, `TELEGRAM_BOT_TOKEN` in GH Secrets + CF Worker Secrets (auto-sync via `deploy-bot.yml`)
- **No credential on repo**: .env never committed, .gitignore covers
- **Data privacy**: bot không lưu conversation (stateless, optional KV memory phục vụ context 30 min)
- **HTTPS only**: Cloudflare enforce HTTPS, Worker requests always SSL

### NFR5: Scalability
- **Serverless design**: no server maintain, only GH Actions + CF Worker + CF KV
- **Topic-agnostic**: add topic chỉ cần sửa config.json, code không đổi
- **Parallelism**: URL check 8 threads, async Telegram push
- **No database**: file-based (cards.json), JSON on GitHub

### NFR6: Maintainability
- **Config-driven**: mỗi topic ~ 10 config lines (search_queries, rss_feeds, instruction, schema)
- **Code clarity**: function names self-documenting, comments for hard logic
- **Version control**: commit message format "morning YYYY-MM-DD" (daily), "weekly YYYY-MM-DD" (weekly), "monthly YYYY-MM-DD" (monthly)
- **Monitoring**: GitHub Actions logs, Telegram notify fail log

### NFR7: Data Retention
- **cards.json**: rolling 30 ngày (oldest entries auto-drop ngoài 30 ngày)
- **weekly.json**: rolling 12 tuần
- **monthly.json**: rolling unlimited (không xoá tháng cũ)
- **KV memory**: TTL 30 phút (auto-delete)

---

## 5. Kiến trúc hệ thống

### Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│                   GitHub (git repo)                          │
│  - config.json, generate_card.py, bot/, workflows/           │
└────────────────────┬─────────────────────────────────────────┘
                     │
        ┌────────────┼────────────┐
        │            │            │
        ▼            ▼            ▼
   ┌─────────┐  ┌──────────┐  ┌───────┐
   │.github/ │  │ Pipeline │  │ Bot   │
   │workflows│  │ (Python) │  │(TS)   │
   └────┬────┘  └────┬─────┘  └───┬───┘
        │            │            │
    (on schedule)    │            │(on push bot/)
        │            │            │
        └────────┬───┴────────────┘
                 │
    ┌────────────▼────────────┐
    │  GitHub Actions Runner  │
    │  (generate_card.py etc) │
    └────────────┬────────────┘
                 │
        ┌────────┼────────┐
        ▼        ▼        ▼
    ┌────────┐ ┌──────┐ ┌──────────┐
    │ Gemini │ │ Jina │ │ GitHub   │
    │ 2.5    │ │Search│ │ Search   │
    │ flash  │ │ API  │ │ API      │
    └────────┘ └──────┘ └──────────┘
        │        │        │
        └────────┼────────┘
                 │
        ┌────────▼────────┐
        │  cards.json     │
        │ (git + GitHub   │
        │  Pages CDN)     │
        └────────┬────────┘
                 │
        ┌────────┼────────┐
        │        │        │
        ▼        ▼        ▼
    ┌──────┐ ┌─────────┐ ┌──────────┐
    │ Bot  │ │Web site │ │Telegram  │
    │ (CF  │ │(CF      │ │ API      │
    │Worker)│ │Pages)   │ │          │
    └──────┘ └─────────┘ └──────────┘
        │
    ┌───┴───┐
    ▼       ▼
┌────────┐ ┌───┐
│ KV     │ │ — │
│Store   │ │RAG│
└────────┘ └───┘
```

### Data Flow

1. **Daily 9h (UTC+7)**: 
   - Cron trigger `morning.yml`
   - Fetch (Jina + GitHub + RSS)
   - Gemini gen (hard rule: URL from data)
   - HEAD-check URLs (drop dead)
   - Dedup (Jaccard 55%, 7 days)
   - Validate (news must have URL)
   - Write cards.json
   - Push Telegram → notify user

2. **Daily 10h (UTC+7)**:
   - Cron trigger `morning.yml` (recap job)
   - Top 3 items from latest card
   - Push Telegram recap

3. **Weekly (Sunday 9h)**:
   - Dep: needs daily success
   - Load 7 days cards
   - Gemini summarize → weekly.json
   - Push Telegram weekly link

4. **Monthly (1st 9h)**:
   - Dep: needs weekly success
   - Load month data (or backfill specific month)
   - Gemini summarize → monthly.json

5. **Bot user message**:
   - Webhook POST `/webhook`
   - Fetch latest cards.json from GitHub Pages
   - RAG or command handler
   - LLM response (Gemini/OpenAI)
   - Telegram send reply
   - KV store: memory + rate-limit counter

### Components

| Component | Tech | Role |
|---|---|---|
| `generate_card.py` | Python 3.11 | Orchestrator daily: fetch → Gemini → validate → write |
| `jina_fetch.py` | Python + Jina API | Search: Jina Search + GitHub Search |
| `rss_fetch.py` | Python + feedparser | Fetch RSS/Atom feeds |
| `digest_utils.py` | Python | Utilities: dedup, URL check, validate |
| `generate_weekly.py` | Python + Gemini | Summarize 7 days → weekly.json |
| `generate_monthly.py` | Python + Gemini | Summarize month → monthly.json |
| `notify-telegram.py` | Python + Telegram API | Push digest + recap to Telegram |
| `bot/src/index.ts` | TypeScript (CF Worker) | Webhook handler, routing |
| `bot/src/rag.ts` | TypeScript | Fetch + BM25 retrieval from cards |
| `bot/src/commands.ts` | TypeScript | Command handlers (/digest, /topic, etc) |
| `bot/src/llm/gemini.ts` | TypeScript + Gemini | Chat + response gen |
| `bot/src/llm/openai.ts` | TypeScript + OpenAI | GPT-4o, image, whisper |
| `index.html` | HTML/CSS/JS | Web site render cards.json |
| `.github/workflows/` | YAML | CI/CD automation |

---

## 6. Data Model

### cards.json (Daily)
```json
[
  {
    "date": "2026-07-13",
    "dayLabel": "Chủ Nhật",
    "dateLabel": "13/07/2026",
    "tech": [
      {
        "title": "📱 iPhone 16 Pro ra mắt với chip A18",
        "desc": "Apple công bố iPhone 16 Pro với chip A18 mới, camera AI, pin 30h. Giá từ 29 triệu VND.",
        "tag": "launch",
        "tagLabel": "🚀 LAUNCH",
        "source": "13/07 · genk.vn",
        "url": "https://genk.vn/..."
      }
    ],
    "finance": [...],
    "entertainment": [...],
    "gaming": [...],
    "vietnam": [...],
    "lifestyle": [...]
  },
  ...  // rolling 30 ngày
]
```

### weekly.json (Weekly)
```json
[
  {
    "weekLabel": "Tuần 29/2026",
    "weekNum": 29,
    "year": 2026,
    "fromDate": "2026-07-07",
    "toDate": "2026-07-13",
    "tech": [...],  // top items từ 7 days
    "finance": [...],
    ...
  },
  ...  // rolling 12 tuần
]
```

### monthly.json (Monthly)
```json
[
  {
    "monthLabel": "Tháng 7/2026",
    "month": 7,
    "year": 2026,
    "tech": [...],  // top items từ tháng
    "finance": [...],
    ...
  },
  ...  // rolling unlimited
]
```

### config.json (Configuration)
```json
{
  "site": {
    "title": "🐟 Cá Mặn Đau Lưng",
    "tagline": "Tin cho người 3x · Sáng 9h · Recap 10h",
    "logo": "🐟",
    "footer": "..."
  },
  "telegram": {
    "chat_ids": ["655323886", "782194719"]
  },
  "topics": {
    "tech_gadget": {
      "enabled": true,
      "data_source": "jina",
      "output_field": "tech",
      "emoji": "📱",
      "section_label": "Tech & Gadget",
      "min_items": 3,
      "max_items": 5,
      "search_queries": [...],
      "rss_feeds": [...],
      "prompt_instruction": "...",
      "schema": "{...}"
    },
    ...  // 6 topics total
  },
  "tone_guidance": "..."
}
```

### Dedup Index (in-memory, per run)
```python
exact_norms: set[str]  # normalized titles exact match
tokens_list: list[set[str]]  # content-bearing tokens per title
threshold: float = 0.55  # Jaccard >= 55% = duplicate
```

### KV Store (Cloudflare Workers)
```json
{
  "memory:{user_id}:{ts}": {
    "role": "user|assistant",
    "content": "...",
    "timestamp": "ISO8601"
  },
  "ratelimit:{user_id}:{hour}": {
    "count": 15,  // messages this hour
    "limit": 60
  }
}
```

---

## 7. Vận hành (Operations)

### Deployment
1. **Code change** → push to main
2. **GitHub Actions triggers**:
   - `morning.yml`: cron schedule (daily 9h, 10h recap, Sun 9h weekly, 1st 9h monthly)
   - `deploy-bot.yml`: on push, if `bot/**` changed → wrangler deploy
   - `deploy-cloudflare-pages.yml`: on push main → deploy site
3. **Secrets sync**: `deploy-bot.yml` auto-sync GH secrets to CF Worker env

### Cron Schedule (Vietnam time UTC+7)

| Time | Action | File | Cron (UTC) | Cron (UTC+7) |
|---|---|---|---|---|
| 9:00 AM | Daily digest | generate_card.py | `0 2 * * *` | `0 9 * * *` |
| 10:00 AM | Recap push | notify-telegram.py | `0 3 * * *` | `0 10 * * *` |
| Sun 9:00 AM | Weekly summary | generate_weekly.py | `0 2 * * 0` | `0 9 * * 0` |
| 1st 9:00 AM | Monthly summary | generate_monthly.py | `0 2 1 * *` | `0 9 1 * *` |

### Manual Triggers (workflow_dispatch)
- `run_weekly=true` → force weekly digest
- `run_monthly=true` → force monthly digest
- `backfill_month=YYYY-MM` → generate specific month (skip daily if set)

### Monitoring & Logs
- **GitHub Actions**: Check workflow logs in `.github/workflows/`
- **Telegram**: `notify-telegram.py` logs push success/fail
- **Bot**: `wrangler logs` + Cloudflare dashboard
- **URL validation**: `digest_utils.py` print dropped URLs (dead link, blacklist)
- **Dedup**: log "dedup: {title}" for each duplicate dropped

### Failure Modes & Recovery
| Failure | Cause | Recovery |
|---|---|---|
| Gemini API timeout | Network / quota | Retry in next run (GH Actions native retry) |
| URL dead link | Link changed/removed | Logged + dropped, next card continues |
| Telegram notify fail | Bot token invalid / network | Log error, don't block card write |
| Duplicate detection miss | Jaccard < 0.55 | Rare, user may see paraphrase; log for review |
| Worker deploy fail | Syntax error in bot/ | Fix + re-push, auto-retry |
| KV storage full | Unlikely (free tier huge) | Archive old KV keys manually |

---

## 8. Rủi ro & giả định

### Risks
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Gemini hallucinate URL | Medium | User click fake link | HARD RULE: URL from data only; HEAD-check all |
| RSS feed dead | Medium | Miss news source | Fallback to Jina Search; update config quarterly |
| Jina API quota hit | Low | No news for that topic | Graceful fallback: empty array allowed |
| GitHub Actions quota | Very low (free tier huge) | Digest delay | N/A — GitHub Actions free tier very generous |
| Duplicate not caught (Jaccard < 0.55) | Low | User see repeat | Dedup window 7 days sufficient; rare edge case |
| Telegram webhook timeout | Low | User miss digest | Retry queue + manual trigger (workflow_dispatch) |
| URL HEAD-check slow | Low | Digest delay | Parallel 8 threads + timeout; async allowed |
| Bot KV memory leak | Low | Rate-limit fail | TTL 30 min auto-cleanup; manual sweep if needed |

### Assumptions
1. **Gemini 2.5 flash stable**: Model available, pricing consistent
2. **OpenAI APIs stable**: gpt-4o, gpt-image-1, whisper-1 available
3. **Jina Search API** stable (free tier sufficient for 6 topics daily)
4. **GitHub Actions cron reliable**: Proven 99%+ uptime
5. **Cloudflare Worker uptime 99.95%**: SLA trusted
6. **RSS/Jina feeds responsive**: < 10s fetch per source
7. **Telegram Bot API stable**: Standard Telegram uptime
8. **User engagement**: 2 active users (Anh + Anh Lê); may scale to small group

---

## 9. Roadmap & Hướng phát triển (Đề xuất)

### Phase 1: MVP (DONE ✓)
- Daily digest pipeline (Gemini + dedup + HEAD-check)
- Weekly/monthly rollup
- Chatbot basic commands
- Telegram push + recap

### Phase 2: Enhancement (Next 2-3 tháng)
- [ ] User preference config (per-user topic selection) — need minimal DB or GH config
- [ ] Batch notification (daily digest as 6 separate messages, 1 per topic)
- [ ] Bot: `/save <topic>` → bookmark tin để xem sau
- [ ] Web site: interactive digest view (filter by topic, search, share)
- [ ] Metrics dashboard (# of items per topic, # dedup, # dead URL, response time)

### Phase 3: Expansion (3-6 tháng)
- [ ] More LLM sources: Claude API for better summarization
- [ ] Bot: `/poll <question>` → poll user feedback on quality
- [ ] Integration: Slack channel mirror (for teams)
- [ ] Browser extension: save to Pocket/Notion from digest
- [ ] Newsletter: email digest for non-Telegram users

### Phase 4: Monetization / Scaling (6+ tháng)
- [ ] Premium tier: more topics, custom queries, priority support
- [ ] Corporate feed: company-specific news channel
- [ ] Bot API: allow other projects to plug into digest

---

## 10. Câu hỏi chưa được giải đáp (Unresolved Questions)

1. **Long-term user growth**: Bây giờ 2 users (Anh + Anh Lê). Nếu scale >10 users, có cần user management system không? Hay vẫn hardcode chat IDs?
   - **Proposal**: Nếu <50 users, giữ hardcode. Nếu >50, migrate to Supabase/Firebase for user config.

2. **User personalization**: Hiện tại config cứng (6 topics cho tất cả). Có muốn support "user A chỉ thích tech+finance, user B thích entertainment+gaming" không?
   - **Proposal**: Phase 2 — add minimal user config (GH config file per user, or KV store).

3. **Cost scaling**: Nếu 100 users, Gemini + OpenAI có thể chạy ~$5/mo. Có accept được không?
   - **Proposal**: Yes, vẫn rẻ. Nếu >1000 users, cân nhắc self-hosted LLM (Ollama).

4. **Data retention**: Hiện rolling 30 ngày. Có muốn archive cards.json to S3/GCS for long-term analytics không?
   - **Proposal**: Phase 2 — add monthly archive snapshot (gzip JSON to GH releases).

5. **Feed quality metric**: Hiện không measure "user satisfaction" hoặc "CTR on links". Có muốn add polling / click-tracking không?
   - **Proposal**: Privacy-first — avoid tracking. Nếu muốn, add optional Telegram poll after digest.

6. **RSS feed health**: Có monitoring script để check liveness of RSS feeds periodically không?
   - **Proposal**: Add weekly health-check job (curl HEAD each RSS URL, log dead ones).

7. **Gemini version pinning**: Hiện dùng Gemini 2.5 flash (latest). Có commit to stable version (e.g., "gemini-2.5-flash-001") không?
   - **Proposal**: Pin version after GA; fallback to 2.0 nếu 2.5 unavailable.

8. **Topic schema flexibility**: Mỗi topic có custom schema (JSON string). Có risk người config sai format không? Validate schema khi load config?
   - **Proposal**: Add JSON schema validator (`jsonschema` lib) khi load config.json.

9. **Telegram media support**: Bot hiện text-based. Có muốn support inline image/video từ digest không?
   - **Proposal**: Phase 2 — parse `imageUrl` field in news item, send inline Telegram photo.

10. **Backup & disaster recovery**: cards.json/weekly.json/monthly.json stored trên GitHub. Nếu repo deleted, data lost. Có backup strategy không?
    - **Proposal**: Weekly archive to S3 bucket (managed via GitHub Secrets); retention 1 year.

---

**Document ownership**: Business Analyst  
**Next review**: 2026-10-13 (quarterly)
