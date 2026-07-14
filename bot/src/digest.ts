// Fetch + cache digest data (cards / weekly / monthly / config) from GH Pages
import type { DigestData, DailyCard, WeeklyCard, MonthlyCard } from './types';
import { fetchJson } from './http';

const TTL_SEC = 300; // 5 min
const DIGEST_TIMEOUT_MS = 10000;

interface DigestConfig { topics?: Record<string, unknown>; site?: Record<string, unknown>; }

function fetchDigestJson<T>(url: string): Promise<T | null> {
  return fetchJson<T>(url, { cf: { cacheEverything: true, cacheTtl: TTL_SEC } }, DIGEST_TIMEOUT_MS);
}

export async function loadDigest(base: string): Promise<DigestData> {
  const [daily, weekly, monthly, config] = await Promise.all([
    fetchDigestJson<DailyCard[]>(`${base}/cards.json`),
    fetchDigestJson<WeeklyCard[]>(`${base}/weekly.json`),
    fetchDigestJson<MonthlyCard[]>(`${base}/monthly.json`),
    fetchDigestJson<DigestConfig>(`${base}/config.json`),
  ]);
  return {
    daily:   daily   || [],
    weekly:  weekly  || [],
    monthly: monthly || [],
    config:  config  || { topics: {}, site: {} },
  };
}
