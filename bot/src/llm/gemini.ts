// Gemini 2.5 flash — primary LLM for cheap fast chat + vision (photo describe/OCR)
import type { Msg } from '../types';
import { fetchWithTimeout } from '../http';

const API = 'https://generativelanguage.googleapis.com/v1beta/models';
const LLM_TIMEOUT_MS = 20000;

interface GeminiPart { text?: string; thought?: boolean; inlineData?: { mimeType: string; data: string }; }
interface GeminiContent { role: 'user' | 'model'; parts: GeminiPart[]; }
interface GeminiCandidate { content?: { parts?: GeminiPart[] }; finishReason?: string; }
interface GeminiResp { candidates?: GeminiCandidate[]; error?: { message: string }; }

function extractText(j: GeminiResp): string | null {
  const parts = j.candidates?.[0]?.content?.parts ?? [];
  const text = parts.filter(p => p.text && !p.thought).map(p => p.text).join('').trim();
  return text || null;
}

export async function geminiChat(
  apiKey: string, model: string, system: string, history: Msg[], userText: string,
): Promise<string | null> {
  const contents: GeminiContent[] = [];
  for (const m of history) {
    contents.push({ role: m.role === 'assistant' ? 'model' : 'user', parts: [{ text: m.text }] });
  }
  contents.push({ role: 'user', parts: [{ text: userText }] });

  const body = {
    systemInstruction: { parts: [{ text: system }] },
    contents,
    generationConfig: { temperature: 0.5, maxOutputTokens: 1024 },
  };

  try {
    const r = await fetchWithTimeout(`${API}/${model}:generateContent?key=${apiKey}`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
    }, LLM_TIMEOUT_MS);
    const j = await r.json() as GeminiResp;
    if (j.error) { console.error('[gemini]', j.error.message); return null; }
    return extractText(j);
  } catch (e) {
    console.error('[gemini] fetch error:', e);
    return null;
  }
}

// Describe/OCR an image. base64Image = raw base64 (no data: prefix).
export async function geminiDescribeImage(
  apiKey: string, model: string, base64Image: string, mimeType: string, question: string,
): Promise<string | null> {
  const contents: GeminiContent[] = [{
    role: 'user',
    parts: [
      { text: question },
      { inlineData: { mimeType, data: base64Image } },
    ],
  }];
  const body = { contents, generationConfig: { temperature: 0.4, maxOutputTokens: 512 } };

  try {
    const r = await fetchWithTimeout(`${API}/${model}:generateContent?key=${apiKey}`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
    }, LLM_TIMEOUT_MS);
    const j = await r.json() as GeminiResp;
    if (j.error) { console.error('[gemini vision]', j.error.message); return null; }
    return extractText(j);
  } catch (e) {
    console.error('[gemini vision] fetch error:', e);
    return null;
  }
}
