"""Shared Gemini API client — call + retry + text/grounding extraction.
Single source of truth for both generate_card.py (grounding search fallback,
thinking_budget=2048) and generate_weekly.py (thinking_budget=0, no search) — see H2.
GEMINI_API_KEY is read from env only, never logged."""
import os
from google import genai
from google.genai import types

_client = None  # lazy singleton — avoids requiring GEMINI_API_KEY at import time


def get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    return _client


def call_gemini(
    prompt: str,
    use_search: bool = False,
    thinking_budget: int = 2048,
    max_output_tokens: int = 8192,
    temperature: float = 0.3,
    retries: int = 2,
    model: str = "gemini-2.5-flash",
) -> tuple[str | None, set[str]]:
    """Call Gemini with retry. Returns (text, grounding_urls).
    use_search=True enables Google Search grounding tool (real citation URLs,
    used as fallback when pre-fetched context has no data)."""
    client = get_client()
    tools = [types.Tool(google_search=types.GoogleSearch())] if use_search else []
    for attempt in range(retries + 1):
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=tools,
                    temperature=temperature,
                    max_output_tokens=max_output_tokens,
                    thinking_config=types.ThinkingConfig(thinking_budget=thinking_budget),
                )
            )

            text_parts = []
            grounding_urls = set()
            if response.candidates:
                cand = response.candidates[0]
                for part in (cand.content.parts or []):
                    if hasattr(part, "thought") and part.thought:
                        continue
                    if hasattr(part, "text") and part.text:
                        text_parts.append(part.text)
                # Extract grounding citations (real source URLs from Google Search)
                gm = getattr(cand, "grounding_metadata", None)
                if gm:
                    for chunk in (getattr(gm, "grounding_chunks", None) or []):
                        web = getattr(chunk, "web", None)
                        if web and getattr(web, "uri", None):
                            grounding_urls.add(web.uri)

            text = "\n".join(text_parts).strip()
            if text:
                print(f"  Attempt {attempt+1}: got {len(text)} chars, {len(grounding_urls)} citations")
                return text, grounding_urls

            finish = "unknown"
            if response.candidates:
                finish = str(response.candidates[0].finish_reason)
            print(f"  Attempt {attempt+1}: empty. Finish: {finish}")

        except Exception as e:
            print(f"  Attempt {attempt+1} error: {e}")

    return None, set()
