"""
處理 CMS 發佈之翻譯 job（Pub/Sub payload 與 HTTP /hooks/sync-translations 相同）。
僅接受 type 為 post / comment，其餘型別拒絕。
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from pydantic import ValidationError

from app.hooks_translate import sync_translations_from_hook
from app.schemas import KeystoneHookSyncTranslationRequest

logger = logging.getLogger(__name__)


def handle_translation_pubsub_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    驗證 payload 並執行 sync_translations_from_hook。
    成功時回傳與 HTTP hook 類似的結果 dict（供 log）。
    """
    try:
        body = KeystoneHookSyncTranslationRequest.model_validate(payload)
    except ValidationError as e:
        raise ValueError(f"invalid translation payload: {e}") from e

    if body.article_type not in ("post", "comment"):
        raise ValueError(
            f"Pub/Sub translation job only supports post|comment, got: {body.article_type!r}"
        )

    return sync_translations_from_hook(
        article_type=body.article_type,
        item_id=body.id,
        source_text=body.source_text,
        source_title=body.source_title,
    )
