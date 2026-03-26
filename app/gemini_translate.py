import json
import logging
from typing import Any, Dict

from .config import get_settings

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """
You are a professional polyglot translator and linguistic expert.
Your task is to analyze a given text snippet and perform the following actions:

1. Detect the original language of the input text (limited to: zh-tw, en, vi, th, id).
2. Translate the input text into ALL five target languages: 'zh-tw' (Traditional Chinese), 'en' (English), 'vi' (Vietnamese), 'th' (Thai), and 'id' (Indonesian).

### Strict Constraints:
- RESPONSE FORMAT: Return ONLY a valid JSON object. No Markdown blocks (```json), no pre-ambles, and no post-explanations.
- LANGUAGE CODES: Use exactly these keys: 'zh-tw', 'en', 'vi', 'th', 'id'.
- PRESERVATION: Even if the source language matches a target, provide it in the corresponding field.
- TONE: Natural, professional, and culturally appropriate.

### JSON Output Schema:
{
  "detect-lang": "string",
  "translation": {
    "zh-tw": "string",
    "en": "string",
    "vi": "string",
    "th": "string",
    "id": "string"
  }
}
"""


def translate_and_detect(text: str) -> Dict[str, Any]:
    import google.generativeai as genai

    settings = get_settings()
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY 環境變數未設定")

    genai.configure(api_key=settings.gemini_api_key)

    model = genai.GenerativeModel(
        model_name=settings.gemini_model,
        system_instruction=_SYSTEM_PROMPT,
        generation_config={
            "response_mime_type": "application/json",
            "temperature": 0.2,
        },
    )

    user_prompt = f"""
Please process the following text according to the JSON schema defined above:

---
Input Text:
"{text}"
---
"""

    response = model.generate_content(user_prompt)
    raw = getattr(response, "text", None) or ""
    if not raw.strip():
        raise RuntimeError("Gemini 回傳空內容")

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        logger.warning("Gemini 非合法 JSON: %s", raw[:500])
        raise RuntimeError(f"Gemini 回傳非合法 JSON: {e}") from e
