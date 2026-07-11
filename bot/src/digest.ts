// Fetch + cache digest data (cards / weekly / monthly / config) from GH Pages
import type { DigestData, DailyCard, WeeklyCard, MonthlyCard } from './types';

const TTL_SEC = 300; // 5 min

async function fetchJson<T>(url: string): Promise<T | null> {
  try {
    const r = await fetch(url, { cf: { cacheEverything: true, cacheTtl: TTL_SEC } as any });
    if (!r.ok) return null;
    return await r.json() as T;
  } catch (e) {
    console.error(`[digest] fetch fail ${url}:`, e);
    return null;
  }
}

export async function loadDigest(base: string): Promise<DigestData> {
  const [daily, weekly, monthly, config] = await Promise.all([
    fetchJson<DailyCard[]>(`${base}/cards.json`),
    fetchJson<WeeklyCard[]>(`${base}/weekly.json`),
    fetchJson<MonthlyCard[]>(`${base}/monthly.json`),
    fetchJson<any>(`${base}/config.json`),
  ]);
  return {
    daily:   daily   || [],
    weekly:  weekly  || [],
    monthly: monthly || [],
    config:  config  || { topics: {}, site: {} },
  };
}
