// Rau Bot — Cloudflare Worker entry.
// Handles Telegram webhook POSTs, routes to commands / free-text chat / voice / URL summary.

import type { Env } from './types';
import { sendMessage, sendPhoto, sendChatAction, getFileUrl, esc } from './telegram';
import { isAllowed } from './access';
import { loadDigest } from './digest';
import { getHistory, appendHistory, checkRateLimit } from './memory';
import { geminiChat } from './llm/gemini';
import { openaiTranscribe } from './llm/openai';
import { systemPrompt } from './llm/persona';
import { retrieveContext, formatContextForPrompt } from './rag';
import { extractFirstUrl, summarizeUrl } from './url-summary';
import {
  cmdStart, cmdHelp, cmdDigest, cmdTopic, cmdWeek, cmdMonth,
  cmdDeep, cmdImg, cmdClear,
} from './commands';

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);

    // Health check
    if (request.method === 'GET' && url.pathname === '/') {
      return new Response(`caman-bot up. hooked to https://t.me/${env.BOT_USERNAME}`, { status: 200 });
    }

    if (url.pathname !== '/webhook' || request.method !== 'POST') {
      return new Response('Not found', { status: 404 });
    }

    // Verify Telegram webhook secret
    const gotSecret = request.headers.get('X-Telegram-Bot-Api-Secret-Token');
    if (env.TELEGRAM_WEBHOOK_SECRET && gotSecret !== env.TELEGRAM_WEBHOOK_SECRET) {
      return new Response('forbidden', { status: 403 });
    }

    let update: any;
    try { update = await request.json(); }
    catch { return new Response('bad json', { status: 400 }); }

    // Fire and forget — return 200 fast so Telegram doesn't retry
    ctx.waitUntil(handleUpdate(update, env).catch(e => console.error('[handle]', e)));
    return new Response('ok', { status: 200 });
  },
};

async function handleUpdate(update: any, env: Env): Promise<void> {
  const msg = update.message || update.edited_message;
  if (!msg) return;

  const chatId = msg.chat?.id;
  const userId = msg.from?.id;
  if (!chatId || !userId) return;

  const token = env.TELEGRAM_BOT_TOKEN;

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
    const fileUrl = await getFileUrl(token, msg.voice.file_id);
    if (fileUrl) {
      const audioBlob = await (await fetch(fileUrl)).blob();
      const t = await openaiTranscribe(env.OPENAI_API_KEY, env.OPENAI_STT_MODEL, audioBlob, 'voice.ogg');
      if (t) {
        text = t;
        await sendMessage(token, chatId, `🎤 <i>Em nghe: "${esc(t)}"</i>`);
      } else {
        await sendMessage(token, chatId, '😅 Không nghe rõ voice, anh/chị gõ text giúp em nhé.');
        return;
      }
    }
  }

  if (!text) {
    await sendMessage(token, chatId, 'Em chỉ hiểu text/voice. Gửi lại giúp em nhé.');
    return;
  }

  // ── Command routing ──────────────────────────────────────────────────────
  const trimmed = text.trim();

  if (trimmed.startsWith('/')) {
    const [rawCmd, ...rest] = trimmed.split(/\s+/);
    const cmd = rawCmd.split('@')[0].toLowerCase();
    const arg = rest.join(' ');

    let reply: string | null = null;
    let photo: { imageUrl?: string; error?: string } | null = null;

    switch (cmd) {
      case '/start': reply = cmdStart(env); break;
      case '/help':  reply = cmdHelp(env); break;
      case '/clear': reply = await cmdClear(env, userId); break;
      case '/digest': {
        const data = await loadDigest(env.SITE_BASE_URL);
        reply = cmdDigest(data); break;
      }
      case '/topic': {
        const data = await loadDigest(env.SITE_BASE_URL);
        reply = cmdTopic(data, arg); break;
      }
      case '/week': {
        const data = await loadDigest(env.SITE_BASE_URL);
        reply = cmdWeek(data); break;
      }
      case '/month': {
        const data = await loadDigest(env.SITE_BASE_URL);
        reply = cmdMonth(data); break;
      }
      case '/deep': {
        const data = await loadDigest(env.SITE_BASE_URL);
        reply = await cmdDeep(env, data, arg); break;
      }
      case '/img': {
        photo = await cmdImg(env, arg); break;
      }
      default:
        reply = `❓ Không nhận diện lệnh <code>${esc(cmd)}</code>. Gõ /help để xem menu.`;
    }

    if (photo?.imageUrl) {
      await sendPhoto(token, chatId, photo.imageUrl, `🎨 <i>${esc(arg)}</i>`);
    } else if (photo?.error) {
      await sendMessage(token, chatId, photo.error);
    } else if (reply) {
      await sendMessage(token, chatId, reply);
    }
    return;
  }

  // ── URL summary shortcut ─────────────────────────────────────────────────
  const foundUrl = extractFirstUrl(trimmed);
  if (foundUrl && trimmed.length < foundUrl.length + 20) {
    // Message is basically just a URL → summarize
    await sendMessage(token, chatId, '📖 Đang đọc bài viết, chờ em xíu...');
    const summary = await summarizeUrl(foundUrl, env.GEMINI_API_KEY, env.GEMINI_MODEL, env.JINA_API_KEY);
    if (summary) {
      await sendMessage(token, chatId, `${summary}\n\n<a href="${esc(foundUrl)}">Đọc bài gốc ↗</a>`);
      await appendHistory(env.STATE, userId, trimmed, summary);
    } else {
      await sendMessage(token, chatId, '😅 Không đọc được bài này, có thể site chặn bot. Anh/chị copy nội dung gửi em cũng được.');
    }
    return;
  }

  // ── Free-text chat with RAG + memory ─────────────────────────────────────
  const [history, data] = await Promise.all([
    getHistory(env.STATE, userId),
    loadDigest(env.SITE_BASE_URL),
  ]);
  const items = retrieveContext(data, trimmed, 10);
  const ctx = formatContextForPrompt(items);
  const system = systemPrompt(env.SITE_BASE_URL) + `\n\nDIGEST CONTEXT (30 ngày qua, chỉ dùng những gì liệt kê):\n${ctx}`;

  const reply = await geminiChat(env.GEMINI_API_KEY, env.GEMINI_MODEL, system, history, trimmed);
  const finalReply = reply || '😅 Em đang hơi lag, thử lại giúp em nhé.';

  await sendMessage(token, chatId, finalReply);
  if (reply) await appendHistory(env.STATE, userId, trimmed, reply);
}
