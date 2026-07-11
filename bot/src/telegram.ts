// Telegram Bot API wrapper — REST calls to api.telegram.org

const API = 'https://api.telegram.org/bot';

interface TgResp<T = unknown> { ok: boolean; result?: T; description?: string; }

async function call<T>(token: string, method: string, payload: Record<string, unknown>): Promise<T | null> {
  const r = await fetch(`${API}${token}/${method}`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const j = await r.json() as TgResp<T>;
  if (!j.ok) console.error(`[tg] ${method} fail:`, j.description);
  return j.ok ? (j.result ?? null) : null;
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

export function sendPhoto(token: string, chatId: number | string, photoUrl: string, caption = '') {
  return call(token, 'sendPhoto', { chat_id: chatId, photo: photoUrl, caption, parse_mode: 'HTML' });
}

export function sendChatAction(token: string, chatId: number | string, action = 'typing') {
  return call(token, 'sendChatAction', { chat_id: chatId, action });
}

export async function getFileUrl(token: string, fileId: string): Promise<string | null> {
  const file = await call<{ file_path: string }>(token, 'getFile', { file_id: fileId });
  return file ? `https://api.telegram.org/file/bot${token}/${file.file_path}` : null;
}

// HTML escape for reply text
export function esc(s: string): string {
  return (s || '').replace(/[&<>]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' } as Record<string, string>)[c]);
}
