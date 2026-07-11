// Gemini 2.5 flash — primary LLM for cheap fast chat
import type { Msg } from '../types';

const API = 'https://generativelanguage.googleapis.com/v1beta/models';

interface GeminiPart { text?: string; thought?: boolean; }
interface GeminiCandidate { content?: { parts?: GeminiPart[] }; finishReason?: string; }
interface GeminiResp { candidates?: GeminiCandidate[]; error?: { message: string }; }

export async function geminiChat(
  apiKey: string, model: string, system: string, history: Msg[], userText: string,
): Promise<string | null> {
  const contents: any[] = [];
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
    const r = await fetch(`${API}/${model}:generateContent?key=${apiKey}`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
    });
    const j = await r.json() as GeminiResp;
    if (j.error) { console.error('[gemini]', j.error.message); return null; }
    const parts = j.candidates?.[0]?.content?.parts ?? [];
    const text = parts.filter(p => p.text && !p.thought).map(p => p.text).join('').trim();
    return text || null;
  } catch (e) {
    console.error('[gemini] fetch error:', e);
    return null;
  }
}
