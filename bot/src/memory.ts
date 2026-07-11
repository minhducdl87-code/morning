// Per-user conversation memory + rate limit — both KV-backed
import type { Msg } from './types';

const HISTORY_TTL_SEC = 1800;    // 30 min idle → auto-expire
const HISTORY_MAX_MSGS = 12;      // 6 turns (user + bot pairs)
const RATE_WINDOW_SEC  = 3600;
const RATE_MAX         = 60;      // 60 msgs / hour / user

// ── History ──────────────────────────────────────────────────────────────────

export async function getHistory(kv: KVNamespace, userId: number | string): Promise<Msg[]> {
  const raw = await kv.get(`chat:${userId}`, 'json');
  return Array.isArray(raw) ? (raw as Msg[]) : [];
}

export async function appendHistory(kv: KVNamespace, userId: number | string, userText: string, botText: string): Promise<void> {
  const cur = await getHistory(kv, userId);
  cur.push({ role: 'user', text: userText });
  cur.push({ role: 'assistant', text: botText });
  const trimmed = cur.slice(-HISTORY_MAX_MSGS);
  await kv.put(`chat:${userId}`, JSON.stringify(trimmed), { expirationTtl: HISTORY_TTL_SEC });
}

export async function clearHistory(kv: KVNamespace, userId: number | string): Promise<void> {
  await kv.delete(`chat:${userId}`);
}

// ── Rate limit ───────────────────────────────────────────────────────────────

export async function checkRateLimit(kv: KVNamespace, userId: number | string): Promise<{ ok: boolean; remaining: number }> {
  const key = `rl:${userId}`;
  const raw = await kv.get(key);
  const count = raw ? parseInt(raw, 10) : 0;
  if (count >= RATE_MAX) return { ok: false, remaining: 0 };
  await kv.put(key, String(count + 1), { expirationTtl: RATE_WINDOW_SEC });
  return { ok: true, remaining: RATE_MAX - count - 1 };
}
