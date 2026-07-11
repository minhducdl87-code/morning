// RAG helper — extract relevant items from digest based on user query
import type { DigestData, DigestItem, DailyCard, WeeklyCard, MonthlyCard } from './types';

const VN_STOPWORDS = new Set([
  'và','của','với','để','cho','là','có','bị','được','đã','sẽ','đang','một','các','những',
  'này','đó','về','từ','trong','ngoài','trên','dưới','hoặc','hay','khi','nếu','thì','vì',
  'bởi','do','giờ','đến','tại','theo','như','the','a','an','of','to','for','with','in',
  'on','at','and','or','but','is','are','was','were','be','have','has','had','tôi','em','anh',
  'gì','sao','thế','nào','bao','giờ','nhé','ạ','không','có','ko','ai','đâu','làm','ra','cần',
]);

function tokens(s: string): Set<string> {
  const norm = (s || '')
    .toLowerCase()
    .replace(/[^\p{L}\p{N}\s]/gu, ' ')
    .split(/\s+/)
    .filter(w => w.length > 1 && !VN_STOPWORDS.has(w));
  return new Set(norm);
}

// Score item vs query: intersection size + boost if URL/title exact substring match
function scoreItem(item: DigestItem, queryTokens: Set<string>, queryRaw: string): number {
  const bag = tokens(`${item.title || ''} ${item.name || ''} ${item.desc || ''} ${item.reason || ''}`);
  let overlap = 0;
  for (const t of queryTokens) if (bag.has(t)) overlap++;
  const substrBoost = queryRaw && (item.title?.toLowerCase().includes(queryRaw) || item.name?.toLowerCase().includes(queryRaw)) ? 3 : 0;
  return overlap + substrBoost;
}

function listFields<T extends Record<string, any>>(obj: T): string[] {
  return Object.keys(obj).filter(k =>
    Array.isArray(obj[k]) && !['date','dayLabel','dateLabel','fromDate','toDate','monthLabel','weekLabel'].includes(k)
  );
}

// Grab top N items across daily/weekly/monthly ranked by query relevance
export function retrieveContext(data: DigestData, query: string, topK = 12): DigestItem[] {
  const qTokens = tokens(query);
  const qRaw = query.toLowerCase().trim();
  const pool: DigestItem[] = [];

  const collect = (arr: (DailyCard|WeeklyCard|MonthlyCard)[]) => {
    for (const card of arr) {
      for (const f of listFields(card as any)) {
        const items = (card as any)[f] as DigestItem[];
        for (const it of items) if (it?.title || it?.name) pool.push(it);
      }
    }
  };
  collect(data.daily); collect(data.weekly); collect(data.monthly);

  // Dedup by URL, keep first
  const seen = new Set<string>();
  const uniq: DigestItem[] = [];
  for (const it of pool) {
    const k = (it.url || it.title || it.name || '').toLowerCase();
    if (k && !seen.has(k)) { seen.add(k); uniq.push(it); }
  }

  // No query terms → return most recent (pool is already daily→weekly→monthly newest first)
  if (qTokens.size === 0) return uniq.slice(0, topK);

  const scored = uniq
    .map(it => ({ it, score: scoreItem(it, qTokens, qRaw) }))
    .filter(x => x.score > 0)
    .sort((a, b) => b.score - a.score);

  return scored.slice(0, topK).map(x => x.it);
}

export function formatContextForPrompt(items: DigestItem[]): string {
  if (!items.length) return '(Không có tin liên quan trong digest 30 ngày qua.)';
  return items.map((it, i) => {
    const title = it.title || it.name || '';
    const desc = (it.desc || it.reason || '').slice(0, 150);
    return `[${i+1}] ${title}\n    URL: ${it.url || ''}\n    ${desc}`;
  }).join('\n');
}
