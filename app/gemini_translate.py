import json
import logging
from functools import lru_cache
from typing import Any, Dict, Optional

from .config import get_settings

logger = logging.getLogger(__name__)


class GeminiBlockedError(ValueError):
    """Gemini 因內容政策擋下翻譯請求。"""


_COPYRIGHT_FALLBACK_INSTRUCTION = """

SAFETY FALLBACK:
- If a literal translation would reproduce copyrighted text or otherwise trigger policy blocks, do not translate line-by-line.
- Instead, provide a concise paraphrased translation in each target language that preserves the original meaning without closely reproducing the wording.
- Keep the same JSON schema and language keys.
"""


@lru_cache(maxsize=8)
def _cached_generative_model(model_name: str, system_instruction: str) -> Any:
    """
    依模型名稱與 system instruction 快取 GenerativeModel，重用底層連線／client。
    （不同 prompt 必須分開快取，因 system_instruction 在建立時固定。）
    """
    import google.generativeai as genai

    settings = get_settings()
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY 環境變數未設定")

    genai.configure(api_key=settings.gemini_api_key)
    return genai.GenerativeModel(
        model_name=model_name,
        system_instruction=system_instruction,
        generation_config={
            "response_mime_type": "application/json",
            "temperature": 0.2,
        },
    )


def _response_finish_reason(response: Any) -> Optional[int]:
    candidates = getattr(response, "candidates", None)
    if not candidates:
        return None

    first = candidates[0]
    finish_reason = getattr(first, "finish_reason", None)
    if finish_reason is None:
        return None
    if isinstance(finish_reason, int):
        return finish_reason

    for value in (finish_reason, getattr(finish_reason, "value", None)):
        try:
            if value is not None:
                return int(value)
        except (TypeError, ValueError):
            continue
    return None


def _response_debug_details(response: Any) -> str:
    details: list[str] = []
    finish_reason = _response_finish_reason(response)
    if finish_reason is not None:
        details.append(f"finish_reason={finish_reason}")

    prompt_feedback = getattr(response, "prompt_feedback", None)
    block_reason = getattr(prompt_feedback, "block_reason", None)
    if block_reason is not None:
        details.append(f"block_reason={block_reason}")

    return ", ".join(details)


def _extract_response_text(response: Any) -> str:
    try:
        raw = getattr(response, "text", None) or ""
    except Exception as e:  # noqa: BLE001
        finish_reason = _response_finish_reason(response)
        if finish_reason == 4:
            raise GeminiBlockedError(
                "Gemini blocked literal translation as possible copyrighted material"
            ) from e

        detail = _response_debug_details(response)
        suffix = f" ({detail})" if detail else ""
        raise RuntimeError(f"Gemini response accessor failed{suffix}: {e}") from e

    if raw.strip():
        return raw

    finish_reason = _response_finish_reason(response)
    if finish_reason == 4:
        raise GeminiBlockedError(
            "Gemini blocked literal translation as possible copyrighted material"
        )

    detail = _response_debug_details(response)
    suffix = f" ({detail})" if detail else ""
    raise RuntimeError(f"Gemini 回傳空內容{suffix}")


def _call_gemini_json(system_instruction: str, user_prompt: str) -> Dict[str, Any]:
    settings = get_settings()
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY 環境變數未設定")

    model = _cached_generative_model(settings.gemini_model, system_instruction)
    try:
        raw = _extract_response_text(model.generate_content(user_prompt))
    except GeminiBlockedError:
        logger.info("Gemini translation blocked; retrying with paraphrase fallback")
        fallback_model = _cached_generative_model(
            settings.gemini_model,
            system_instruction + _COPYRIGHT_FALLBACK_INSTRUCTION,
        )
        try:
            raw = _extract_response_text(fallback_model.generate_content(user_prompt))
        except GeminiBlockedError as e:
            raise GeminiBlockedError(
                "Gemini blocked translation because the text appears to reproduce copyrighted material"
            ) from e

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        logger.warning("Gemini 非合法 JSON: %s", raw[:500])
        raise RuntimeError(f"Gemini 回傳非合法 JSON: {e}") from e

_SYSTEM_PROMPT = """
You are a professional polyglot translator and linguistic expert.
Your task is to analyze a given text snippet and perform the following actions:

1. Detect the original language of the input text (limited to: zh-tw, en, vi, th, id).
2. Translate the input text into ALL five target languages: 'zh-tw' (Traditional Chinese), 'en' (English), 'vi' (Vietnamese), 'th' (Thai), and 'id' (Indonesian).
3. Estimate a SPAM likelihood score for the input text:
   - spamScore must be a number in [0, 1]
   - 0 means definitely not spam, 1 means definitely spam

### Strict Constraints:
- RESPONSE FORMAT: Return ONLY a valid JSON object. No Markdown blocks (```json), no pre-ambles, and no post-explanations.
- LINE BREAKS: You MUST preserve the original paragraph structure and line breaks from the input text. Within JSON strings, represent line breaks using the literal `\n` character (escaped newline), and do NOT remove or collapse newlines.
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
  },
  "spamScore": 0.0
}
"""


_SYSTEM_PROMPT_MERGED_POST = """
You are a professional polyglot translator and linguistic expert.
You will receive TWO inputs: TITLE and BODY (both non-empty).

For TITLE:
1. Detect the original language (limited to: zh-tw, en, vi, th, id).
2. Translate TITLE into ALL five target languages: 'zh-tw', 'en', 'vi', 'th', 'id'.

For BODY:
1. Detect the original language (limited to: zh-tw, en, vi, th, id).
2. Translate BODY into ALL five target languages: 'zh-tw', 'en', 'vi', 'th', 'id'.
3. Estimate a SPAM likelihood score for the BODY text only:
   - spamScore must be a number in [0, 1]
   - 0 means definitely not spam, 1 means definitely spam

### Strict Constraints:
- RESPONSE FORMAT: Return ONLY a valid JSON object. No Markdown blocks (```json), no pre-ambles, and no post-explanations.
- LINE BREAKS: Preserve paragraph structure and line breaks in each translated string; use literal `\\n` in JSON strings where needed.
- LANGUAGE CODES: Use exactly these keys: 'zh-tw', 'en', 'vi', 'th', 'id'.
- PRESERVATION: Even if the source language matches a target, provide it in the corresponding field.
- TONE: Natural, professional, and culturally appropriate.

### JSON Output Schema:
{
  "title": {
    "detect-lang": "string",
    "translation": {
      "zh-tw": "string",
      "en": "string",
      "vi": "string",
      "th": "string",
      "id": "string"
    }
  },
  "content": {
    "detect-lang": "string",
    "translation": {
      "zh-tw": "string",
      "en": "string",
      "vi": "string",
      "th": "string",
      "id": "string"
    },
    "spamScore": 0.0
  }
}
"""

_SYSTEM_PROMPT_MERGED_CONTENT = """
You are a professional polyglot translator and linguistic expert.
You will receive TWO inputs: TITLE and BODY (both non-empty).

For TITLE:
1. Detect the original language (limited to: zh-tw, en, vi, th, id).
2. Translate TITLE into ALL five target languages: 'zh-tw', 'en', 'vi', 'th', 'id'.

For BODY:
1. Detect the original language (limited to: zh-tw, en, vi, th, id).
2. Translate BODY into ALL five target languages: 'zh-tw', 'en', 'vi', 'th', 'id'.

### Strict Constraints:
- RESPONSE FORMAT: Return ONLY a valid JSON object. No Markdown blocks (```json), no pre-ambles, and no post-explanations.
- LINE BREAKS: Preserve paragraph structure and line breaks in each translated string; use literal `\\n` in JSON strings where needed.
- LANGUAGE CODES: Use exactly these keys: 'zh-tw', 'en', 'vi', 'th', 'id'.
- PRESERVATION: Even if the source language matches a target, provide it in the corresponding field.
- TONE: Natural, professional, and culturally appropriate.

### JSON Output Schema:
{
  "title": {
    "detect-lang": "string",
    "translation": {
      "zh-tw": "string",
      "en": "string",
      "vi": "string",
      "th": "string",
      "id": "string"
    }
  },
  "content": {
    "detect-lang": "string",
    "translation": {
      "zh-tw": "string",
      "en": "string",
      "vi": "string",
      "th": "string",
      "id": "string"
    }
  }
}
"""


def translate_and_detect(text: str) -> Dict[str, Any]:
    user_prompt = f"""
Please process the following text according to the JSON schema defined above:

---
Input Text:
"{text}"
---
"""
    return _call_gemini_json(_SYSTEM_PROMPT, user_prompt)


def translate_title_and_content_merged(
    title: str,
    content: str,
    *,
    include_spam_for_body: bool,
) -> Dict[str, Any]:
    """
    單次 Gemini 請求同時翻譯 title 與正文（兩者皆須非空）。
    回傳結構與單次 translate_and_detect 相容：title / content 各為一組
    detect-lang、translation（以及 Post 正文可含 spamScore）。
    """
    t = (title or "").strip()
    c = (content or "").strip()
    if not t or not c:
        raise ValueError("translate_title_and_content_merged 需要 title 與 content 皆非空")

    system = (
        _SYSTEM_PROMPT_MERGED_POST if include_spam_for_body else _SYSTEM_PROMPT_MERGED_CONTENT
    )
    user_prompt = f"""
Process TITLE and BODY according to the JSON schema defined above.

---
TITLE:
{t}
---
BODY:
{c}
---
"""
    raw = _call_gemini_json(system, user_prompt)
    if not isinstance(raw, dict):
        raise RuntimeError("Gemini 合併回傳非 JSON 物件")

    title_part = raw.get("title")
    content_part = raw.get("content")
    if not isinstance(title_part, dict) or not isinstance(content_part, dict):
        raise RuntimeError("Gemini 合併回傳缺少 title 或 content 物件")
    if not isinstance(title_part.get("translation"), dict):
        raise RuntimeError("Gemini 合併回傳 title 缺少 translation")
    if not isinstance(content_part.get("translation"), dict):
        raise RuntimeError("Gemini 合併回傳 content 缺少 translation")

    return {"title": title_part, "content": content_part}
