// handleUpdate: gate → rate limit → normalize msg (voice/photo/text) → dispatch.
// Order preserved from the original index.ts to avoid changing observable behavior.
import type { Env } from './types';
import type { TgMessage, TgUpdate } from './telegram-types';
import { getUpdateMessage } from './telegram-types';
import { sendMessage, sendChatAction } from './telegram';
import { isAllowed } from './access';
import { checkRateLimit } from './memory';
import { transcribeVoice } from './handlers/voice-handler';
import { handlePhoto } from './handlers/photo-handler';
import { routeCommand } from './handlers/command-router';
import { tryUrlSummary } from './handlers/url-handler';
import { handleChat } from './handlers/chat-handler';

export async function handleUpdate(update: TgUpdate, env: Env): Promise<void> {
  const msg = getUpdateMessage(update);
  if (!msg) return;

  const chatId = msg.chat?.id;
  const userId = msg.from?.id;
  if (!chatId || !userId) return;

  const token = env.TELEGRAM_BOT_TOKEN;

  // M7: any unexpected throw below still gets a friendly reply instead of silence.
  try {
    await dispatch(msg, chatId, userId, env, token);
  } catch (e) {
    console.error('[router] dispatch error:', e);
    await sendMessage(token, chatId, '😅 Có lỗi xảy ra, anh/chị thử lại sau nhé.').catch(() => {});
  }
}

async function dispatch(msg: TgMessage, chatId: number, userId: number, env: Env, token: string): Promise<void> {
  // Whitelist gate (private bot)
  if (!isAllowed(chatId, env.ALLOWED_CHAT_IDS)) {
    await sendMessage(token, chatId, '🔒 Bot riêng, chỉ dành cho tài khoản được cấp quyền.');
    return;
  }

  // Rate limit
  const rl = await checkRateLimit(env.STATE, userId);
  if (!rl.ok) {
    await sendMessage(token, chatId, '⏱️ Anh/chị đã hỏi hơi nhiều, nghỉ ngơi tí em cũng nghỉ 🐟 (60 msg/giờ). Chờ 1 lát nhé.');
    return;
  }

  // Typing indicator
  sendChatAction(token, chatId, 'typing').catch(() => {});

  // Voice → transcribe → treat as text
  let text: string | undefined = msg.text || msg.caption;
  if (!text && msg.voice) {
    const r = await transcribeVoice(msg, env, token);
    if (r.stop) return;
    text = r.text;
  }

  const trimmed = (text || '').trim();

  // ── Command routing ──────────────────────────────────────────────────────
  if (trimmed.startsWith('/')) {
    await routeCommand(trimmed, chatId, userId, env, token);
    return;
  }

  // ── Photo → vision describe/OCR (Q7) ────────────────────────────────────
  if (msg.photo && msg.photo.length) {
    await handlePhoto(msg, trimmed, env, token);
    return;
  }

  if (!trimmed) {
    await sendMessage(token, chatId, 'Em chỉ hiểu text/voice/ảnh. Gửi lại giúp em nhé.');
    return;
  }

  // ── URL summary shortcut ─────────────────────────────────────────────────
  if (await tryUrlSummary(trimmed, chatId, userId, env, token)) return;

  // ── Free-text chat with RAG + memory ─────────────────────────────────────
  await handleChat(trimmed, chatId, userId, env, token);
}
