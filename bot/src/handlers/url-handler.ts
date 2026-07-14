// Bare-URL shortcut — Jina Reader + Gemini summary
import type { Env } from '../types';
import { sendLongMessage, esc } from '../telegram';
import { extractFirstUrl, summarizeUrl } from '../url-summary';
import { appendHistory } from '../memory';

const URL_TEXT_SLACK = 20; // message is "basically just a URL" if it's not much longer than the URL itself

// Returns true if the message was handled as a URL summary (caller stops further routing).
export async function tryUrlSummary(
  trimmed: string, chatId: number, userId: number, env: Env, token: string,
): Promise<boolean> {
  const foundUrl = extractFirstUrl(trimmed);
  if (!foundUrl || trimmed.length >= foundUrl.length + URL_TEXT_SLACK) return false;

  await sendLongMessage(token, chatId, '📖 Đang đọc bài viết, chờ em xíu...');
  const summary = await summarizeUrl(foundUrl, env.GEMINI_API_KEY, env.GEMINI_MODEL, env.JINA_API_KEY);
  if (summary) {
    await sendLongMessage(token, chatId, `${summary}\n\n<a href="${esc(foundUrl)}">Đọc bài gốc ↗</a>`);
    await appendHistory(env.STATE, userId, trimmed, summary);
  } else {
    await sendLongMessage(token, chatId, '😅 Không đọc được bài này, có thể site chặn bot. Anh/chị copy nội dung gửi em cũng được.');
  }
  return true;
}
