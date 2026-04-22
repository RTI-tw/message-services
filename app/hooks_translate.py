from typing import Any, Dict, Literal, Optional, Tuple

from .gemini_translate import translate_and_detect, translate_title_and_content_merged
from .keystone_gql import execute_gql

ArticleType = Literal[
    "post",
    "comment",
    "topic",
    "poll",
    "pollOption",
    "content",
    "forbiddenKeyword",
]

LOW_RISK_SPAM_SCORE = 0.5
HIGH_RISK_SPAM_SCORE = 0.8
POST_REJECT_STATUS = "reject"
COMMENT_REJECT_STATUS = "reject"

QUERY_POST = """
query PostForTranslate($id: ID!) {
  post(where: { id: $id }) {
    id
    title
    content
    language
    status
  }
}
"""

QUERY_COMMENT = """
query CommentForTranslate($id: ID!) {
  comment(where: { id: $id }) {
    id
    content
    language
    status
  }
}
"""

QUERY_TOPIC = """
query TopicForTranslate($id: ID!) {
  topic(where: { id: $id }) {
    id
    name
    language
  }
}
"""

QUERY_POLL = """
query PollForTranslate($id: ID!) {
  poll(where: { id: $id }) {
    id
    title
  }
}
"""

QUERY_POLL_OPTION = """
query PollOptionForTranslate($id: ID!) {
  pollOption(where: { id: $id }) {
    id
    text
  }
}
"""

QUERY_CONTENT = """
query ContentForTranslate($id: ID!) {
  content(where: { id: $id }) {
    id
    title
    content
    language
  }
}
"""

QUERY_FORBIDDEN_KEYWORD = """
query ForbiddenKeywordForTranslate($id: ID!) {
  forbiddenKeyword(where: { id: $id }) {
    id
    word
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

MUTATION_UPDATE_TOPIC = """
mutation UpdateTopicTranslations($id: ID!, $data: TopicUpdateInput!) {
  updateTopic(where: { id: $id }, data: $data) {
    id
  }
}
"""

MUTATION_UPDATE_POLL = """
mutation UpdatePollTranslations($id: ID!, $data: PollUpdateInput!) {
  updatePoll(where: { id: $id }, data: $data) {
    id
  }
}
"""

MUTATION_UPDATE_POLL_OPTION = """
mutation UpdatePollOptionTranslations($id: ID!, $data: PollOptionUpdateInput!) {
  updatePollOption(where: { id: $id }, data: $data) {
    id
  }
}
"""

MUTATION_UPDATE_CONTENT = """
mutation UpdateContentTranslations($id: ID!, $data: ContentUpdateInput!) {
  updateContent(where: { id: $id }, data: $data) {
    id
  }
}
"""

MUTATION_UPDATE_FORBIDDEN_KEYWORD = """
mutation UpdateForbiddenKeywordTranslations($id: ID!, $data: ForbiddenKeywordUpdateInput!) {
  updateForbiddenKeyword(where: { id: $id }, data: $data) {
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


def _translation_to_prefixed_fields(
    field_prefix: str, translation: Dict[str, Any]
) -> Dict[str, Any]:
    """Gemini translation keys -> Keystone GraphQL snake_case（content_zh / name_zh / title_zh / text_zh / word_zh）。"""
    out: Dict[str, Any] = {
        f"{field_prefix}_zh": translation.get("zh-tw")
        if "zh-tw" in translation
        else translation.get("zh_tw"),
        f"{field_prefix}_en": translation.get("en"),
        f"{field_prefix}_vi": translation.get("vi"),
        f"{field_prefix}_th": translation.get("th"),
        f"{field_prefix}_id": translation.get("id"),
    }
    return {k: v for k, v in out.items() if v is not None}


def _field_prefix_for_entity(entity: ArticleType) -> str:
    if entity in ("post", "comment", "content"):
        return "content"
    if entity == "topic":
        return "name"
    if entity == "poll":
        return "title"
    if entity == "pollOption":
        return "text"
    if entity == "forbiddenKeyword":
        return "word"
    raise ValueError(f"unknown entity: {entity}")


def _entity_supports_language_field(entity: ArticleType) -> bool:
    return entity in ("post", "comment", "topic", "content", "forbiddenKeyword")


def _entity_supports_spam_score(entity: ArticleType) -> bool:
    return entity in ("post", "comment")


def _post_status_for_score(
    entity: ArticleType, spam_score: float, current_status: Optional[str] = None
) -> Optional[str]:
    """Map Gemini risk score to Keystone status. Keystone currently uses `reject`."""
    if entity != "post":
        return None

    if spam_score > HIGH_RISK_SPAM_SCORE:
        return POST_REJECT_STATUS
    if current_status == "pending":
        if spam_score < LOW_RISK_SPAM_SCORE:
            return "published"
        return "pending"
    if current_status == "published":
        return "published"

    return None


def _comment_status_for_score(
    spam_score: float, current_status: Optional[str] = None
) -> Optional[str]:
    if spam_score > HIGH_RISK_SPAM_SCORE:
        return COMMENT_REJECT_STATUS
    if current_status == "pending":
        if spam_score < LOW_RISK_SPAM_SCORE:
            return "published"
        return "pending"
    if current_status == "published":
        return "published"
    return None


def _build_update_data(
    entity: ArticleType,
    gemini_result: Dict[str, Any],
    source_text: str,
    current_status: Optional[str] = None,
) -> Dict[str, Any]:
    trans = gemini_result.get("translation")
    if not isinstance(trans, dict):
        raise ValueError("Gemini 回傳缺少 translation")

    prefix = _field_prefix_for_entity(entity)
    data = _translation_to_prefixed_fields(prefix, trans)

    lang = gemini_detect_to_keystone_language(
        gemini_result.get("detect-lang") or gemini_result.get("detect_lang")
    )

    if _entity_supports_spam_score(entity):
        spam_score = gemini_result.get("spamScore")
        if spam_score is not None:
            try:
                v = float(spam_score)
                v = max(0.0, min(1.0, v))
                data["spamScore"] = v
                if entity == "post":
                    moderation_status = _post_status_for_score(
                        entity, v, current_status
                    )
                    if moderation_status:
                        data["status"] = moderation_status
                elif entity == "comment":
                    moderation_status = _comment_status_for_score(v, current_status)
                    if moderation_status:
                        data["status"] = moderation_status
            except (TypeError, ValueError):
                pass

    if lang and _entity_supports_language_field(entity):
        data["language"] = lang
        detected_field_map = {
            "zh": f"{prefix}_zh",
            "en": f"{prefix}_en",
            "vi": f"{prefix}_vi",
            "th": f"{prefix}_th",
            "id": f"{prefix}_id",
        }
        detected_field = detected_field_map.get(lang)
        if detected_field:
            data[detected_field] = source_text

    return data


def _build_title_update_data(
    gemini_result: Dict[str, Any],
    source_title: str,
) -> Dict[str, Any]:
    trans = gemini_result.get("translation")
    if not isinstance(trans, dict):
        raise ValueError("Gemini 回傳缺少 translation（title）")

    data = _translation_to_prefixed_fields("title", trans)
    lang = gemini_detect_to_keystone_language(
        gemini_result.get("detect-lang") or gemini_result.get("detect_lang")
    )
    if lang:
        detected_field_map = {
            "zh": "title_zh",
            "en": "title_en",
            "vi": "title_vi",
            "th": "title_th",
            "id": "title_id",
        }
        detected_field = detected_field_map.get(lang)
        if detected_field:
            data[detected_field] = source_title
    return data


def _fetch_content_source_texts(item_id: str) -> Tuple[str, str]:
    """與 _fetch_post_source_texts 相同語意：讀取靜態頁 title／content 原文。"""
    data = execute_gql(QUERY_CONTENT, {"id": item_id})
    node = data.get("content")
    if not node:
        raise ValueError(f"content id={item_id} 不存在")

    title = (node.get("title") or "").strip()
    content = (node.get("content") or "").strip()
    if not title and not content:
        raise ValueError("title 與 content 皆為空，無法翻譯")
    return title, content


def _sync_post_or_content_translations(
    article_type: Literal["post", "content"],
    item_id: str,
    source_text: Optional[str],
    source_title: Optional[str],
    source_status: Optional[str] = None,
) -> Dict[str, Any]:
    """Post／Content：翻譯正文（content_*）與標題（title_*）。title 與 content 皆有時改為單次 Gemini 合併請求。"""
    update_data: Dict[str, Any] = {}
    title = (source_title or "").strip()
    content = (source_text or "").strip()
    fetch_pair = (
        _fetch_post_source_texts
        if article_type == "post"
        else _fetch_content_source_texts
    )
    current_status = (source_status or "").strip() or None
    if not title and not content:
        title, content = fetch_pair(item_id)
        if article_type == "post":
            current_status = _fetch_current_status(article_type, item_id)
    elif not title or not content:
        fetched_title, fetched_content = fetch_pair(item_id)
        if not title:
            title = fetched_title
        if not content:
            content = fetched_content
        if article_type == "post":
            current_status = _fetch_current_status(article_type, item_id)
    elif article_type == "post" and current_status is None:
        current_status = _try_fetch_current_status(article_type, item_id)

    if content and title:
        merged = translate_title_and_content_merged(
            title,
            content,
            include_spam_for_body=(article_type == "post"),
        )
        update_data.update(
            _build_update_data(
                article_type, merged["content"], content, current_status
            )
        )
        update_data.update(_build_title_update_data(merged["title"], title))
    elif content:
        content_result = translate_and_detect(content)
        update_data.update(
            _build_update_data(article_type, content_result, content, current_status)
        )
    elif title:
        title_result = translate_and_detect(title)
        update_data.update(_build_title_update_data(title_result, title))
    return update_data


_FETCH_CONFIG: Dict[ArticleType, Tuple[str, str, str]] = {
    "post": (QUERY_POST, "post", "content"),
    "comment": (QUERY_COMMENT, "comment", "content"),
    "topic": (QUERY_TOPIC, "topic", "name"),
    "poll": (QUERY_POLL, "poll", "title"),
    "pollOption": (QUERY_POLL_OPTION, "pollOption", "text"),
    "content": (QUERY_CONTENT, "content", "content"),
    "forbiddenKeyword": (QUERY_FORBIDDEN_KEYWORD, "forbiddenKeyword", "word"),
}


def _fetch_source_text(article_type: ArticleType, item_id: str) -> str:
    query, node_key, field = _FETCH_CONFIG[article_type]
    data = execute_gql(query, {"id": item_id})
    node = data.get(node_key)
    if not node:
        raise ValueError(f"{article_type} id={item_id} 不存在")
    text = (node.get(field) or "").strip()
    if not text:
        raise ValueError(
            f"{field} 為空，無法翻譯（請在 CMS 填寫原文或改傳 source_text）"
        )
    return text


def _fetch_current_status(article_type: ArticleType, item_id: str) -> Optional[str]:
    if article_type not in ("post", "comment"):
        return None

    query, node_key, _field = _FETCH_CONFIG[article_type]
    data = execute_gql(query, {"id": item_id})
    node = data.get(node_key)
    if not node:
        raise ValueError(f"{article_type} id={item_id} 不存在")
    status = node.get("status")
    return str(status) if status else None


def _try_fetch_current_status(article_type: ArticleType, item_id: str) -> Optional[str]:
    try:
        return _fetch_current_status(article_type, item_id)
    except ValueError as e:
        if "不存在" in str(e):
            return None
        raise


def _fetch_post_source_texts(item_id: str) -> Tuple[str, str]:
    data = execute_gql(QUERY_POST, {"id": item_id})
    node = data.get("post")
    if not node:
        raise ValueError(f"post id={item_id} 不存在")

    title = (node.get("title") or "").strip()
    content = (node.get("content") or "").strip()
    if not title and not content:
        raise ValueError("title 與 content 皆為空，無法翻譯")
    return title, content


def sync_translations_from_hook(
    *,
    article_type: ArticleType,
    item_id: str,
    source_text: Optional[str] = None,
    source_title: Optional[str] = None,
    source_status: Optional[str] = None,
) -> Dict[str, Any]:
    """
    以 Gemini 翻譯後，透過 GQL update* 寫入 language（若有）與各語系欄位。
    """
    update_data: Dict[str, Any] = {}

    if article_type in ("post", "content"):
        update_data = _sync_post_or_content_translations(
            article_type, item_id, source_text, source_title, source_status
        )
    else:
        text = (source_text or "").strip()
        current_status = (source_status or "").strip() or None
        if text and article_type in ("post", "comment") and current_status is None:
            current_status = _try_fetch_current_status(article_type, item_id)
        if not text:
            text = _fetch_source_text(article_type, item_id)
            if article_type in ("post", "comment"):
                current_status = _fetch_current_status(article_type, item_id)
        gemini_result = translate_and_detect(text)
        update_data = _build_update_data(
            article_type,
            gemini_result,
            text,
            current_status,
        )

    if article_type == "post":
        execute_gql(MUTATION_UPDATE_POST, {"id": item_id, "data": update_data})
    elif article_type == "comment":
        execute_gql(MUTATION_UPDATE_COMMENT, {"id": item_id, "data": update_data})
    elif article_type == "topic":
        execute_gql(MUTATION_UPDATE_TOPIC, {"id": item_id, "data": update_data})
    elif article_type == "poll":
        execute_gql(MUTATION_UPDATE_POLL, {"id": item_id, "data": update_data})
    elif article_type == "pollOption":
        execute_gql(MUTATION_UPDATE_POLL_OPTION, {"id": item_id, "data": update_data})
    elif article_type == "content":
        execute_gql(MUTATION_UPDATE_CONTENT, {"id": item_id, "data": update_data})
    elif article_type == "forbiddenKeyword":
        execute_gql(
            MUTATION_UPDATE_FORBIDDEN_KEYWORD,
            {"id": item_id, "data": update_data},
        )
    else:
        raise ValueError(f"unsupported article_type: {article_type}")

    return {
        "id": item_id,
        "type": article_type,
        "updated_fields": list(update_data.keys()),
        "detect_lang": update_data.get("language"),
    }
