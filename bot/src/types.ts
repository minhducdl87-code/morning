// Shared types + env binding

export interface Env {
  // KV
  STATE: KVNamespace;

  // Public vars (wrangler.toml [vars])
  BOT_USERNAME: string;
  SITE_BASE_URL: string;
  ALLOWED_CHAT_IDS: string;
  GEMINI_MODEL: string;
  OPENAI_CHAT_MODEL: string;
  OPENAI_DEEP_MODEL: string;
  OPENAI_IMAGE_MODEL: string;
  OPENAI_STT_MODEL: string;

  // Secrets (wrangler secret put NAME)
  TELEGRAM_BOT_TOKEN: string;
  TELEGRAM_WEBHOOK_SECRET: string;
  GEMINI_API_KEY: string;
  OPENAI_API_KEY: string;
  JINA_API_KEY?: string;
}

export interface Msg {
  role: 'user' | 'assistant';
  text: string;
}

export interface DigestItem {
  title?: string;
  name?: string;
  desc?: string;
  url?: string;
  tag?: string;
  tagLabel?: string;
  source?: string;
  stars?: string;
  verdict?: string;
  reason?: string;
}

export interface DailyCard {
  date: string;
  dayLabel?: string;
  dateLabel?: string;
  [field: string]: string | DigestItem[] | undefined;
}

export interface WeeklyCard {
  weekLabel: string;
  fromDate: string;
  toDate: string;
  [field: string]: string | DigestItem[];
}

export interface MonthlyCard {
  monthLabel: string;
  fromDate: string;
  toDate: string;
  [field: string]: string | DigestItem[];
}

export interface DigestData {
  daily: DailyCard[];
  weekly: WeeklyCard[];
  monthly: MonthlyCard[];
  config: any;
}
