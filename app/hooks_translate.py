from typing import Any, Dict, Literal, Optional

from .gemini_translate import translate_and_detect
from .keystone_gql import execute_gql

ArticleType = Literal["post", "comment"]

QUERY_POST = """
query PostForTranslate($id: ID!) {
  post(where: { id: $id }) {
    id
    content
    language
  }
}
"""

QUERY_COMMENT = """
query CommentForTranslate($id: ID!) {
  comment(where: { id: $id }) {
    id
    content
    language
  }
}
"""

MUTATION_UPDATE_POST = """
mutation UpdatePostTranslations($id: ID!, $data: PostUpdateInput!) {
  updatePost(where: { id: $id }, data: $data) {
    id
  }
}
"""

MUTATION_UPDATE_COMMENT = """
mutation UpdateCommentTranslations($id: ID!, $data: CommentUpdateInput!) {
  updateComment(where: { id: $id }, data: $data) {
    id
  }
}
"""


def gemini_detect_to_keystone_language(detect: Optional[str]) -> Optional[str]:
    if not detect:
        return None
    x = str(detect).lower().strip()
    if x in ("zh-tw", "zh_tw", "zh-hant", "zh-hk", "zh", "cmn"):
        return "zh"
    if x in ("en", "english"):
        return "en"
    if x in ("vi", "vie", "vietnamese"):
        return "vi"
    if x in ("th", "tha", "thai"):
        return "th"
    if x in ("id", "ind", "indonesian"):
        return "id"
    return None


def _translation_to_keystone_content_fields(translation: Dict[str, Any]) -> Dict[str, Any]:
    """Gemini translation keys -> Keystone GraphQL input 欄位（snake_case）。"""
    # Keystone GraphQL input 欄位通常維持跟 schema 相同的命名（本專案為 snake_case）。
    out: Dict[str, Any] = {
        "content_zh": translation.get("zh-tw") if "zh-tw" in translation else translation.get("zh_tw"),
        "content_en": translation.get("en"),
        "content_vi": translation.get("vi"),
        "content_th": translation.get("th"),
        "content_id": translation.get("id"),
    }
    return {k: v for k, v in out.items() if v is not None}


def _build_update_data(gemini_result: Dict[str, Any], source_text: str) -> Dict[str, Any]:
    trans = gemini_result.get("translation")
    if not isinstance(trans, dict):
        raise ValueError("Gemini 回傳缺少 translation")

    data = _translation_to_keystone_content_fields(trans)
    lang = gemini_detect_to_keystone_language(
        gemini_result.get("detect-lang") or gemini_result.get("detect_lang")
    )
    if lang:
        data["language"] = lang

        # 原語言欄位使用「原文」（source_text），不要用 Gemini 同語言翻譯結果覆蓋。
        # 例：detect=en => contentEn 使用原文；其他 content_* 使用翻譯值。
        detected_field_map = {
            "zh": "content_zh",
            "en": "content_en",
            "vi": "content_vi",
            "th": "content_th",
            "id": "content_id",
        }
        detected_field = detected_field_map.get(lang)
        if detected_field:
            data[detected_field] = source_text
    return data


def _fetch_source_content(article_type: ArticleType, item_id: str) -> str:
    if article_type == "post":
        data = execute_gql(QUERY_POST, {"id": item_id})
        node = data.get("post")
    else:
        data = execute_gql(QUERY_COMMENT, {"id": item_id})
        node = data.get("comment")

    if not node:
        raise ValueError(f"{article_type} id={item_id} 不存在")
    content = (node.get("content") or "").strip()
    if not content:
        raise ValueError("content 為空，無法翻譯（請在 CMS 填寫「原文內容」或改傳 source_text）")
    return content


def sync_translations_from_hook(
    *,
    article_type: ArticleType,
    item_id: str,
    source_text: Optional[str] = None,
) -> Dict[str, Any]:
    """
    以 Gemini 翻譯後，透過 GQL updatePost / updateComment 寫入 language 與 content_* 欄位（snake_case）。
    Hook 認證（選填）在 FastAPI route 依賴中處理。
    """
    text = (source_text or "").strip()
    if not text:
        text = _fetch_source_content(article_type, item_id)

    gemini_result = translate_and_detect(text)
    update_data = _build_update_data(gemini_result, text)

    if article_type == "post":
        execute_gql(MUTATION_UPDATE_POST, {"id": item_id, "data": update_data})
    else:
        execute_gql(MUTATION_UPDATE_COMMENT, {"id": item_id, "data": update_data})

    return {
        "id": item_id,
        "type": article_type,
        "updated_fields": list(update_data.keys()),
        "detect_lang": gemini_result.get("detect-lang") or gemini_result.get("detect_lang"),
    }
