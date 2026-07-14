// OpenAI wrapper: chat (fallback + /deep), whisper (voice), image gen
import type { Msg } from '../types';
import { fetchWithTimeout } from '../http';
import { base64ToBytes } from '../binary';

const CHAT_URL   = 'https://api.openai.com/v1/chat/completions';
const IMAGE_URL  = 'https://api.openai.com/v1/images/generations';
const AUDIO_URL  = 'https://api.openai.com/v1/audio/transcriptions';

const CHAT_TIMEOUT_MS  = 20000;
const IMAGE_TIMEOUT_MS = 30000; // image gen is slower than chat
const AUDIO_TIMEOUT_MS = 20000;

interface ChatMessage { role: string; content: string; }
interface ChatResp { choices?: { message?: { content?: string } }[]; error?: { message: string }; }

export async function openaiChat(
  apiKey: string, model: string, system: string, history: Msg[], userText: string,
): Promise<string | null> {
  const messages: ChatMessage[] = [{ role: 'system', content: system }];
  for (const m of history) messages.push({ role: m.role, content: m.text });
  messages.push({ role: 'user', content: userText });

  try {
    const r = await fetchWithTimeout(CHAT_URL, {
      method: 'POST',
      headers: { 'content-type': 'application/json', authorization: `Bearer ${apiKey}` },
      body: JSON.stringify({ model, messages, temperature: 0.5, max_tokens: 1024 }),
    }, CHAT_TIMEOUT_MS);
    const j = await r.json() as ChatResp;
    if (j.error) { console.error('[openai chat]', j.error.message); return null; }
    return j.choices?.[0]?.message?.content?.trim() || null;
  } catch (e) {
    console.error('[openai chat] fetch error:', e);
    return null;
  }
}

interface ImageResp {
  data?: ({ url?: string; b64_json?: string })[];
  error?: { message: string };
}

// error carries the OpenAI failure reason so the caller can surface it
// (private bot → owners want to see why, not a generic message).
export interface ImageResult { url?: string; bytes?: Uint8Array; error?: string; }

// dall-e-3 returns a url; gpt-image-1 returns b64_json only — decode to raw
// bytes so the caller can upload via multipart sendPhoto (data URIs unsupported).
export async function openaiImage(apiKey: string, model: string, prompt: string): Promise<ImageResult> {
  try {
    const r = await fetchWithTimeout(IMAGE_URL, {
      method: 'POST',
      headers: { 'content-type': 'application/json', authorization: `Bearer ${apiKey}` },
      body: JSON.stringify({ model, prompt, n: 1, size: '1024x1024' }),
    }, IMAGE_TIMEOUT_MS);
    const j = await r.json() as ImageResp;
    if (j.error) { console.error('[openai image]', j.error.message); return { error: j.error.message }; }
    const d = j.data?.[0];
    if (d?.url) return { url: d.url };
    if (d?.b64_json) return { bytes: base64ToBytes(d.b64_json) };
    return { error: 'OpenAI trả về rỗng (không có url/b64)' };
  } catch (e) {
    console.error('[openai image] fetch error:', e);
    const isAbort = e instanceof Error && e.name === 'AbortError';
    return { error: isAbort ? 'timeout (>30s)' : (e instanceof Error ? e.message : String(e)) };
  }
}

interface WhisperResp { text?: string; error?: { message: string }; }

// Transcribe voice/audio → text. audioBlob is fetched Telegram file (OGG usually).
export async function openaiTranscribe(
  apiKey: string, model: string, audioBlob: Blob, filename = 'voice.ogg',
): Promise<string | null> {
  try {
    const form = new FormData();
    form.append('file', audioBlob, filename);
    form.append('model', model);
    form.append('language', 'vi');
    const r = await fetchWithTimeout(AUDIO_URL, {
      method: 'POST',
      headers: { authorization: `Bearer ${apiKey}` },
      body: form,
    }, AUDIO_TIMEOUT_MS);
    const j = await r.json() as WhisperResp;
    if (j.error) { console.error('[whisper]', j.error.message); return null; }
    return j.text?.trim() || null;
  } catch (e) {
    console.error('[whisper] fetch error:', e);
    return null;
  }
}
