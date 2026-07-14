// Free-text chat: RAG over digest + memory, Gemini primary / OpenAI fallback (Q6)
import type { Env } from '../types';
import { sendLongMessage } from '../telegram';
import { getHistory, appendHistory } from '../memory';
import { geminiChat } from '../llm/gemini';
import { openaiChat } from '../llm/openai';
import { systemPrompt } from '../llm/persona';
import { retrieveContext, formatContextForPrompt } from '../rag';
import { loadDigest } from '../digest';

const RAG_TOP_K = 10;

export async function handleChat(trimmed: string, chatId: number, userId: number, env: Env, token: string): Promise<void> {
  const [history, data] = await Promise.all([
    getHistory(env.STATE, userId),
    loadDigest(env.SITE_BASE_URL),
  ]);
  const items = retrieveContext(data, trimmed, RAG_TOP_K);
  const ragCtx = formatContextForPrompt(items);
  const system = systemPrompt(env.SITE_BASE_URL) + `\n\nDIGEST CONTEXT (30 ngày qua, chỉ dùng những gì liệt kê):\n${ragCtx}`;

  let reply = await geminiChat(env.GEMINI_API_KEY, env.GEMINI_MODEL, system, history, trimmed);
  if (!reply) {
    // Gemini down/erroring — fall back to OpenAI so the user still gets an answer.
    reply = await openaiChat(env.OPENAI_API_KEY, env.OPENAI_CHAT_MODEL, system, history, trimmed);
  }
  const finalReply = reply || '😅 Em đang hơi lag, thử lại giúp em nhé.';

  await sendLongMessage(token, chatId, finalReply);
  if (reply) await appendHistory(env.STATE, userId, trimmed, reply, history);
}
