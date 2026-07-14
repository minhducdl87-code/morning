// Voice message → Whisper transcription flow
import type { Env } from '../types';
import type { TgMessage } from '../telegram-types';
import { getFileUrl, sendLongMessage, esc } from '../telegram';
import { fetchWithTimeout } from '../http';
import { openaiTranscribe } from '../llm/openai';

const AUDIO_FETCH_TIMEOUT_MS = 15000;

export interface VoiceResult { text?: string; stop: boolean; }

// Transcribes msg.voice (if present). `stop: true` means caller must return
// immediately (an error reply was already sent to the user).
export async function transcribeVoice(msg: TgMessage, env: Env, token: string): Promise<VoiceResult> {
  if (!msg.voice) return { stop: false };
  const chatId = msg.chat.id;

  const fileUrl = await getFileUrl(token, msg.voice.file_id);
  if (!fileUrl) return { stop: false }; // fall through to generic "no text" reply, same as before

  const audioBlob = await (await fetchWithTimeout(fileUrl, {}, AUDIO_FETCH_TIMEOUT_MS)).blob();
  const t = await openaiTranscribe(env.OPENAI_API_KEY, env.OPENAI_STT_MODEL, audioBlob, 'voice.ogg');
  if (!t) {
    await sendLongMessage(token, chatId, '😅 Không nghe rõ voice, anh/chị gõ text giúp em nhé.');
    return { stop: true };
  }

  await sendLongMessage(token, chatId, `🎤 <i>Em nghe: "${esc(t)}"</i>`);
  return { text: t, stop: false };
}
