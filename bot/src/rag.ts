// RAG helper — extract relevant items from digest based on user query.
// Applies recency decay + optional hard date filter so old items don't beat
// current-day items on keyword ties.
import type { DigestData, DigestItem, DailyCard, WeeklyCard, MonthlyCard } from './types';

const VN_STOPWORDS = new Set([
  'và','của','với','để','cho','là','có','bị','được','đã','sẽ','đang','một','các','những',
  'này','đó','về','từ','trong','ngoài','trên','dưới','hoặc','hay','khi','nếu','thì','vì',
  'bởi','do','giờ','đến','tại','theo','như','the','a','an','of','to','for','with','in',
  'on','at','and','or','but','is','are','was','were','be','have','has','had','tôi','em','anh',
  'gì','sao','thế','nào','bao','giờ','nhé','ạ','không','có','ko','ai','đâu','làm','ra','cần',
]);

// Tag items with the source card's date so we can apply time-decay later.
type Tagged = DigestItem & { _srcDate: string };

function tokens(s: string): Set<string> {
  const norm = (s || '')
    .toLowerCase()
    .replace(/[^\p{L}\p{N}\s]/gu, ' ')
    .split(/\s+/)
    .filter(w => w.length > 1 && !VN_STOPWORDS.has(w));
  return new Set(norm);
}

// Detect time-window hints in the user query — hard-filter by max age.
// Returns max allowed age in days (Infinity = no filter).
function detectTimeWindow(qRaw: string): number {
  if (/\b(hôm nay|today|hôm qua|yesterday)\b/i.test(qRaw)) return 2;
  if (/\b(tuần này|tuần qua|this week|past week|7 ngày)\b/i.test(qRaw)) return 8;
  if (/\b(tháng này|tháng qua|this month|past month|30 ngày)\b/i.test(qRaw)) return 32;
  if (/\btrending\b/i.test(qRaw)) return 8;   // trending → tuần này
  if (/\bmới nhất\b/i.test(qRaw)) return 3;    // mới nhất → 3 ngày
  return Infinity;
}

function daysBetween(dateStr: string, today: Date): number {
  if (!dateStr) return 9999;
  const d = new Date(dateStr + 'T00:00:00Z');
  if (isNaN(d.getTime())) return 9999;
  const diffMs = today.getTime() - d.getTime();
  return Math.max(0, Math.round(diffMs / 86400000));
}

// Half-life 7 days: today=1.0, week ago=0.5, 2 weeks=0.25, month=~0.06
function recencyWeight(ageDays: number): number {
  return Math.pow(0.5, ageDays / 7);
}

function scoreItem(item: Tagged, queryTokens: Set<string>, queryRaw: string, ageDays: number): number {
  const bag = tokens(`${item.title || ''} ${item.name || ''} ${item.desc || ''} ${item.reason || ''}`);
  let overlap = 0;
  for (const t of queryTokens) if (bag.has(t)) overlap++;
  const substrBoost = queryRaw && (item.title?.toLowerCase().includes(queryRaw) || item.name?.toLowerCase().includes(queryRaw)) ? 3 : 0;
  const base = overlap + substrBoost;
  if (base === 0) return 0;
  return base * recencyWeight(ageDays);
}

function listFields<T extends Record<string, unknown>>(obj: T): string[] {
  return Object.keys(obj).filter(k =>
    Array.isArray(obj[k]) && !['date','dayLabel','dateLabel','fromDate','toDate','monthLabel','weekLabel'].includes(k)
  );
}

// Card → representative date (daily uses .date, weekly/monthly use .toDate).
function cardDate(card: DailyCard | WeeklyCard | MonthlyCard): string {
  return (card as DailyCard).date || (card as WeeklyCard | MonthlyCard).toDate || '';
}

export function retrieveContext(data: DigestData, query: string, topK = 12): DigestItem[] {
  const qTokens = tokens(query);
  const qRaw = query.toLowerCase().trim();
  const today = new Date();
  const maxAge = detectTimeWindow(qRaw);
  const pool: Tagged[] = [];

  const collect = (arr: (DailyCard|WeeklyCard|MonthlyCard)[]) => {
    for (const card of arr) {
      const srcDate = cardDate(card);
      for (const f of listFields(card as unknown as Record<string, unknown>)) {
        const items = (card as unknown as Record<string, DigestItem[]>)[f];
        for (const it of items) if (it?.title || it?.name) pool.push({ ...it, _srcDate: srcDate });
      }
    }
  };
  collect(data.daily); collect(data.weekly); collect(data.monthly);

  // Dedup by URL, keep first (which is newest since data is newest-first)
  const seen = new Set<string>();
  const uniq: Tagged[] = [];
  for (const it of pool) {
    const k = (it.url || it.title || it.name || '').toLowerCase();
    if (k && !seen.has(k)) { seen.add(k); uniq.push(it); }
  }

  // Apply hard time-window filter if query hints at recency
  const filtered = maxAge === Infinity
    ? uniq
    : uniq.filter(it => daysBetween(it._srcDate, today) <= maxAge);

  const workingSet = filtered.length ? filtered : uniq;   // fallback if filter empties pool

  // No query terms → return most recent (sort by srcDate desc, tie-break original order)
  if (qTokens.size === 0) {
    return workingSet
      .slice()
      .sort((a, b) => (b._srcDate || '').localeCompare(a._srcDate || ''))
      .slice(0, topK)
      .map(stripInternal);
  }

  const scored = workingSet
    .map(it => ({ it, score: scoreItem(it, qTokens, qRaw, daysBetween(it._srcDate, today)) }))
    .filter(x => x.score > 0)
    .sort((a, b) => b.score - a.score);

  return scored.slice(0, topK).map(x => stripInternal(x.it));
}

function stripInternal(it: Tagged): DigestItem {
  const { _srcDate: _drop, ...rest } = it;
  return rest;
}

export function formatContextForPrompt(items: DigestItem[]): string {
  if (!items.length) return '(Không có tin liên quan trong digest gần đây.)';
  return items.map((it, i) => {
    const title = it.title || it.name || '';
    const desc = (it.desc || it.reason || '').slice(0, 150);
    return `[${i+1}] ${title}\n    URL: ${it.url || ''}\n    ${desc}`;
  }).join('\n');
}
