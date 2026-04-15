"""
處理 CMS 發佈之翻譯 job（Pub/Sub／HTTP payload 與 /hooks/sync-translations 相同）。
僅接受 type 為 post / comment，其餘型別拒絕。

放在 app 套件內，供 Cloud Run API（Dockerfile 只 COPY app）與 subscriber 共用。
"""

from __future__ import annotations

from typing import Any, Dict

from pydantic import ValidationError

from .hooks_translate import sync_translations_from_hook
from .schemas import KeystoneHookSyncTranslationRequest


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
