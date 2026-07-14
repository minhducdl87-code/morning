// Telegram Bot API wrapper — REST calls to api.telegram.org
import { fetchWithTimeout } from './http';

const API = 'https://api.telegram.org/bot';
const TG_TIMEOUT_MS = 10000;
const TG_MAX_LEN = 4096;

interface TgResp<T = unknown> { ok: boolean; result?: T; description?: string; }

async function call<T>(token: string, method: string, payload: Record<string, unknown>): Promise<T | null> {
  try {
    const r = await fetchWithTimeout(`${API}${token}/${method}`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(payload),
    }, TG_TIMEOUT_MS);
    const j = await r.json() as TgResp<T>;
    if (!j.ok) console.error(`[tg] ${method} fail:`, j.description);
    return j.ok ? (j.result ?? null) : null;
  } catch (e) {
    console.error(`[tg] ${method} fetch error:`, e);
    return null;
  }
}

export function sendMessage(token: string, chatId: number | string, text: string, opts: Record<string, unknown> = {}) {
  return call(token, 'sendMessage', {
    chat_id: chatId,
    text,
    parse_mode: 'HTML',
    disable_web_page_preview: true,
    ...opts,
  });
}

// Telegram caps text messages at 4096 chars — chunk long replies by line
// boundary so digest/RAG/summary replies are never silently dropped.
export async function sendLongMessage(
  token: string, chatId: number | string, text: string, opts: Record<string, unknown> = {},
): Promise<void> {
  if (text.length <= TG_MAX_LEN) {
    await sendMessage(token, chatId, text, opts);
    return;
  }
  for (const chunk of splitByLines(text, TG_MAX_LEN)) {
    await sendMessage(token, chatId, chunk, opts);
  }
}

function splitByLines(text: string, maxLen: number): string[] {
  const lines = text.split('\n');
  const chunks: string[] = [];
  let cur = '';
  for (const line of lines) {
    if (line.length > maxLen) {
      // Single line longer than the whole limit — hard-split it.
      if (cur) { chunks.push(cur); cur = ''; }
      for (let i = 0; i < line.length; i += maxLen) chunks.push(line.slice(i, i + maxLen));
      continue;
    }
    const candidate = cur ? `${cur}\n${line}` : line;
    if (candidate.length > maxLen) {
      chunks.push(cur);
      cur = line;
    } else {
      cur = candidate;
    }
  }
  if (cur) chunks.push(cur);
  return chunks;
}

export function sendPhoto(token: string, chatId: number | string, photoUrl: string, caption = '') {
  return call(token, 'sendPhoto', { chat_id: chatId, photo: photoUrl, caption, parse_mode: 'HTML' });
}

// gpt-image-1 only returns b64_json (no URL) — Telegram's JSON sendPhoto only
// accepts an HTTP URL or file_id, so b64 images must go through multipart
// upload instead.
export async function sendPhotoBlob(
  token: string, chatId: number | string, bytes: Uint8Array, caption = '', mimeType = 'image/png',
): Promise<unknown> {
  try {
    const form = new FormData();
    form.append('chat_id', String(chatId));
    form.append('caption', caption);
    form.append('parse_mode', 'HTML');
    form.append('photo', new Blob([bytes], { type: mimeType }), 'image.png');
    const r = await fetchWithTimeout(`${API}${token}/sendPhoto`, { method: 'POST', body: form }, TG_TIMEOUT_MS);
    const j = await r.json() as TgResp;
    if (!j.ok) console.error('[tg] sendPhoto(blob) fail:', j.description);
    return j.ok ? (j.result ?? null) : null;
  } catch (e) {
    console.error('[tg] sendPhoto(blob) fetch error:', e);
    return null;
  }
}

export function sendChatAction(token: string, chatId: number | string, action = 'typing') {
  return call(token, 'sendChatAction', { chat_id: chatId, action });
}

export async function getFileUrl(token: string, fileId: string): Promise<string | null> {
  const file = await call<{ file_path: string }>(token, 'getFile', { file_id: fileId });
  return file ? `https://api.telegram.org/file/bot${token}/${file.file_path}` : null;
}

// HTML escape for reply text (also covers `"` for safe use inside href="...")
export function esc(s: string): string {
  return (s || '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' } as Record<string, string>)[c]);
}
