"""Extract a JSON dict from raw Gemini text response — strips markdown code fence,
tries direct json.loads, falls back to regex brace-matching. Single source of truth
(was duplicated between generate_card.py and generate_weekly.py — see H2)."""
import json
import re


def parse_llm_json(text: str) -> dict | None:
    """Parse LLM text response into a dict. Returns None if all parsing fails."""
    if not text:
        return None
    text = text.strip()
    text = re.sub(r"^```[a-z]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text).strip()

    try:
        return json.loads(text)
    except Exception as e1:
        print(f"Direct JSON parse failed: {e1}")
        m = re.search(r"\{[\s\S]+\}", text)
        if m:
            try:
                return json.loads(m.group())
            except Exception as e2:
                print(f"Regex JSON parse also failed: {e2}")
    return None
