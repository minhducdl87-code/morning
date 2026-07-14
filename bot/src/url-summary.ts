// URL summarization via Jina Reader → Gemini
import { geminiChat } from './llm/gemini';
import { fetchWithTimeout } from './http';

const URL_RE = /\bhttps?:\/\/[^\s<>()]+/i;
const READER_URL = 'https://r.jina.ai/';
const MAX_CONTENT = 6000;
const JINA_TIMEOUT_MS = 10000;

export function extractFirstUrl(text: string): string | null {
  const m = text.match(URL_RE);
  return m ? m[0] : null;
}

async function fetchReadable(url: string, jinaKey?: string): Promise<string | null> {
  const headers: Record<string, string> = { Accept: 'text/plain', 'X-Return-Format': 'markdown' };
  if (jinaKey) headers.Authorization = `Bearer ${jinaKey}`;
  try {
    const r = await fetchWithTimeout(
      READER_URL + url,
      { headers, cf: { cacheEverything: true, cacheTtl: 600 } },
      JINA_TIMEOUT_MS,
    );
    if (!r.ok) return null;
    const text = await r.text();
    return text.slice(0, MAX_CONTENT);
  } catch (e) {
    console.error('[url-summary] jina fetch:', e);
    return null;
  }
}

export async function summarizeUrl(
  url: string, geminiKey: string, geminiModel: string, jinaKey?: string,
): Promise<string | null> {
  const content = await fetchReadable(url, jinaKey);
  if (!content) return null;

  const system = `Bạn là biên tập viên. Nhiệm vụ: tóm tắt bài viết cho người đọc 30-40 tuổi VN.
Format HTML (Telegram): <b>Tiêu đề gọn</b>, sau đó 3 gạch đầu dòng "• ..." nêu điểm chính,
cuối cùng 1 dòng "<i>Takeaway:</i>" chốt insight. Ngôn ngữ tiếng Việt, câu ngắn, có số liệu.`;
  const user = `URL: ${url}\n\nNội dung bài (đã strip HTML):\n${content}`;
  return geminiChat(geminiKey, geminiModel, system, [], user);
}
