// Shared HTTP layer — fetch with timeout (AbortController) used by every
// external call (Gemini/OpenAI/Jina/Telegram/digest). Prevents Worker from
// hanging inside ctx.waitUntil() when an upstream never responds.

export async function fetchWithTimeout(url: string, opts: RequestInit = {}, timeoutMs = 20000): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...opts, signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

// fetch + parse JSON, swallowing errors (timeout/network/non-2xx) → null.
export async function fetchJson<T>(url: string, opts: RequestInit = {}, timeoutMs = 10000): Promise<T | null> {
  try {
    const r = await fetchWithTimeout(url, opts, timeoutMs);
    if (!r.ok) return null;
    return await r.json() as T;
  } catch (e) {
    console.error(`[http] fetch fail ${url}:`, e);
    return null;
  }
}
