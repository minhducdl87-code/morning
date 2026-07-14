// Photo message → Gemini vision describe/OCR (Q7 feature, promised in menu/README)
import type { Env } from '../types';
import type { TgMessage } from '../telegram-types';
import { getFileUrl, sendLongMessage } from '../telegram';
import { fetchWithTimeout } from '../http';
import { bytesToBase64 } from '../binary';
import { geminiDescribeImage } from '../llm/gemini';

const PHOTO_FETCH_TIMEOUT_MS = 15000;
const DEFAULT_PROMPT = 'Mô tả nội dung ảnh này ngắn gọn bằng tiếng Việt. Nếu ảnh có chữ, OCR và trích lại text quan trọng.';

// question = caption user sent with the photo (may be empty → use default prompt).
export async function handlePhoto(msg: TgMessage, question: string, env: Env, token: string): Promise<void> {
  const chatId = msg.chat.id;
  const sizes = msg.photo;
  if (!sizes || !sizes.length) return;

  // Telegram's photo array is sorted smallest→largest; last = highest resolution.
  const largest = sizes[sizes.length - 1];
  const fileUrl = await getFileUrl(token, largest.file_id);
  if (!fileUrl) {
    await sendLongMessage(token, chatId, '😅 Không tải được ảnh, anh/chị gửi lại giúp em nhé.');
    return;
  }

  try {
    const imgResp = await fetchWithTimeout(fileUrl, {}, PHOTO_FETCH_TIMEOUT_MS);
    const bytes = new Uint8Array(await imgResp.arrayBuffer());
    const base64 = bytesToBase64(bytes);
    const prompt = question.trim() || DEFAULT_PROMPT;
    const desc = await geminiDescribeImage(env.GEMINI_API_KEY, env.GEMINI_MODEL, base64, 'image/jpeg', prompt);
    await sendLongMessage(token, chatId, desc || '😅 Không đọc được ảnh này, thử lại sau ạ.');
  } catch (e) {
    console.error('[photo]', e);
    await sendLongMessage(token, chatId, '😅 Xử lý ảnh gặp lỗi, thử lại sau ạ.');
  }
}
