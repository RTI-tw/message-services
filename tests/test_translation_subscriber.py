"""app.translation_job：Pub/Sub 翻譯 payload 驗證與白名單。"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


def test_handle_translation_pubsub_post_calls_sync(monkeypatch: pytest.MonkeyPatch) -> None:
    called: dict = {}

    def fake_sync(*, article_type, item_id, source_text, source_title):
        called["article_type"] = article_type
        called["item_id"] = item_id
        called["source_text"] = source_text
        called["source_title"] = source_title
        return {"id": item_id, "type": article_type, "updated_fields": []}

    monkeypatch.setattr("app.translation_job.sync_translations_from_hook", fake_sync)

    from app.translation_job import handle_translation_pubsub_payload

    out = handle_translation_pubsub_payload(
        {
            "type": "post",
            "id": "p1",
            "source_text": "body",
            "source_title": "ttl",
        }
    )
    assert out["id"] == "p1"
    assert called == {
        "article_type": "post",
        "item_id": "p1",
        "source_text": "body",
        "source_title": "ttl",
    }


def test_handle_translation_pubsub_comment(monkeypatch: pytest.MonkeyPatch) -> None:
    mock = MagicMock(return_value={"ok": True})
    monkeypatch.setattr("app.translation_job.sync_translations_from_hook", mock)

    from app.translation_job import handle_translation_pubsub_payload

    handle_translation_pubsub_payload({"type": "comment", "id": "c1"})
    mock.assert_called_once_with(
        article_type="comment",
        item_id="c1",
        source_text=None,
        source_title=None,
    )


def test_handle_translation_rejects_topic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.translation_job.sync_translations_from_hook",
        MagicMock(side_effect=AssertionError("should not run")),
    )

    from app.translation_job import handle_translation_pubsub_payload

    with pytest.raises(ValueError, match="post\\|comment"):
        handle_translation_pubsub_payload({"type": "topic", "id": "t1"})


def test_handle_translation_invalid_payload() -> None:
    from app.translation_job import handle_translation_pubsub_payload

    with pytest.raises(ValueError, match="invalid translation payload"):
        handle_translation_pubsub_payload({"type": "post"})
