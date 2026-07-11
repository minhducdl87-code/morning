// Slash command handlers — return HTML reply text
import type { Env, DigestData, DigestItem } from './types';
import { esc } from './telegram';
import { clearHistory } from './memory';
import { openaiChat, openaiImage } from './llm/openai';
import { systemPrompt } from './llm/persona';
import { retrieveContext, formatContextForPrompt } from './rag';

// ── Helpers ──────────────────────────────────────────────────────────────────

function topicMeta(config: any): Record<string, { emoji: string; label: string }> {
  const out: Record<string, { emoji: string; label: string }> = {};
  for (const t of Object.values(config?.topics || {}) as any[]) {
    if (t?.output_field) out[t.output_field] = { emoji: t.emoji || '•', label: t.section_label || t.output_field };
  }
  return out;
}

function fmtItem(it: DigestItem, meta?: { emoji: string }): string {
  const emoji = meta?.emoji || '•';
  const title = esc(it.title || it.name || '');
  const url = it.url;
  const desc = esc((it.desc || '').slice(0, 140));
  const link = url ? `<a href="${esc(url)}"><b>${title}</b></a>` : `<b>${title}</b>`;
  return `${emoji} ${link}${desc ? '\n   ' + desc : ''}`;
}

// ── /start /help ──────────────────────────────────────────────────────────────

export function cmdStart(env: Env): string {
  return `🐟 <b>Cá Mặn Đau Lưng</b>

Em là Rau Bot, trợ lý digest cho anh/chị.

Gõ tin bất kỳ để chat, hoặc:
/digest — bảng tin hôm nay
/topic tech|finance|vietnam|entertainment|gaming|lifestyle
/week — tổng kết tuần
/month — tổng kết tháng
/deep &lt;câu hỏi&gt; — dùng GPT-4o cho câu hỏi khó
/img &lt;prompt&gt; — sinh ảnh
/clear — xóa lịch sử chat
/help — menu

Có thể gửi:
• Voice message → em transcribe rồi trả lời
• Link URL → em tóm bài viết
• Ảnh → em mô tả nội dung

Xem web: ${env.SITE_BASE_URL}`;
}

export function cmdHelp(env: Env): string { return cmdStart(env); }

// ── /digest ──────────────────────────────────────────────────────────────────

export function cmdDigest(data: DigestData): string {
  const card = data.daily[0];
  if (!card) return '📭 Chưa có card daily nào ạ.';
  const meta = topicMeta(data.config);
  const lines: string[] = [`📰 <b>Digest ${esc(card.dateLabel || card.date)}</b> (${esc(card.dayLabel || '')})`, ''];
  for (const [field, arr] of Object.entries(card)) {
    if (!Array.isArray(arr) || !arr.length) continue;
    const m = meta[field] || { emoji: '•', label: field };
    lines.push(`${m.emoji} <b>${esc(m.label)}</b>`);
    for (const it of (arr as DigestItem[]).slice(0, 3)) lines.push(fmtItem(it as DigestItem));
    lines.push('');
  }
  return lines.join('\n');
}

// ── /topic <name> ────────────────────────────────────────────────────────────

export function cmdTopic(data: DigestData, arg: string): string {
  const wanted = arg.trim().toLowerCase();
  if (!wanted) return 'Cú pháp: /topic tech|finance|vietnam|entertainment|gaming|lifestyle';
  const meta = topicMeta(data.config);
  const field = Object.keys(meta).find(f => f.toLowerCase().includes(wanted) || wanted.includes(f.toLowerCase()));
  if (!field) return `Không có topic "${esc(wanted)}". Chọn: ${Object.keys(meta).join(', ')}`;

  const items: DigestItem[] = [];
  for (const card of data.daily.slice(0, 7)) {
    const arr = (card as any)[field];
    if (Array.isArray(arr)) items.push(...arr);
    if (items.length >= 8) break;
  }
  if (!items.length) return `📭 Tuần vừa rồi chưa có tin ${esc(meta[field].label)}.`;

  const m = meta[field];
  const lines = [`${m.emoji} <b>${esc(m.label)}</b> — 7 ngày gần nhất`, ''];
  for (const it of items.slice(0, 6)) lines.push(fmtItem(it));
  return lines.join('\n');
}

// ── /week ────────────────────────────────────────────────────────────────────

export function cmdWeek(data: DigestData): string {
  const w = data.weekly[0];
  if (!w) return '📭 Chưa có weekly digest.';
  const meta = topicMeta(data.config);
  const lines = [`📅 <b>${esc(w.weekLabel)}</b> (${w.fromDate} → ${w.toDate})`, ''];
  for (const [field, arr] of Object.entries(w)) {
    if (!Array.isArray(arr) || !arr.length) continue;
    const m = meta[field] || { emoji: '•', label: field };
    lines.push(`${m.emoji} <b>${esc(m.label)}</b>`);
    for (const it of (arr as DigestItem[]).slice(0, 3)) lines.push(fmtItem(it));
    lines.push('');
  }
  return lines.join('\n');
}

// ── /month ───────────────────────────────────────────────────────────────────

export function cmdMonth(data: DigestData): string {
  const m = data.monthly[0];
  if (!m) return '📭 Chưa có monthly digest.';
  const meta = topicMeta(data.config);
  const lines = [`📆 <b>${esc(m.monthLabel)}</b> (${m.fromDate} → ${m.toDate})`, ''];
  for (const [field, arr] of Object.entries(m)) {
    if (!Array.isArray(arr) || !arr.length) continue;
    const mm = meta[field] || { emoji: '•', label: field };
    lines.push(`${mm.emoji} <b>${esc(mm.label)}</b>`);
    for (const it of (arr as DigestItem[]).slice(0, 3)) lines.push(fmtItem(it));
    lines.push('');
  }
  return lines.join('\n');
}

// ── /deep <question> — OpenAI GPT-4o with RAG ────────────────────────────────

export async function cmdDeep(env: Env, data: DigestData, question: string): Promise<string> {
  if (!question.trim()) return 'Cú pháp: /deep câu hỏi phức tạp anh/chị muốn phân tích sâu.';
  const items = retrieveContext(data, question, 15);
  const ctx = formatContextForPrompt(items);
  const system = systemPrompt(env.SITE_BASE_URL) + `\n\nDIGEST CONTEXT:\n${ctx}`;
  const reply = await openaiChat(env.OPENAI_API_KEY, env.OPENAI_DEEP_MODEL, system, [], question);
  return reply || '😅 Không call được OpenAI, thử lại sau ạ.';
}

// ── /img <prompt> — OpenAI image ─────────────────────────────────────────────

export async function cmdImg(env: Env, prompt: string): Promise<{ imageUrl?: string; error?: string }> {
  if (!prompt.trim()) return { error: 'Cú pháp: /img mô tả ảnh muốn sinh' };
  const url = await openaiImage(env.OPENAI_API_KEY, env.OPENAI_IMAGE_MODEL, prompt);
  return url ? { imageUrl: url } : { error: '😅 Sinh ảnh thất bại, thử lại sau ạ.' };
}

// ── /clear ───────────────────────────────────────────────────────────────────

export async function cmdClear(env: Env, userId: number): Promise<string> {
  await clearHistory(env.STATE, userId);
  return '✅ Đã xóa lịch sử chat.';
}
