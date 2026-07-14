// Validates required env vars/secrets are present before handling a request.
// Never logs values — only the names of missing keys.
import type { Env } from './types';

const REQUIRED_KEYS: (keyof Env)[] = [
  'TELEGRAM_BOT_TOKEN',
  'TELEGRAM_WEBHOOK_SECRET',
  'GEMINI_API_KEY',
  'OPENAI_API_KEY',
  'ALLOWED_CHAT_IDS',
  'SITE_BASE_URL',
  'STATE',
];

export function assertEnv(env: Env): void {
  const missing = REQUIRED_KEYS.filter(k => !env[k]);
  if (missing.length) {
    throw new Error(`Missing required env vars: ${missing.join(', ')}`);
  }
}
