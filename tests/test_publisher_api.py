from __future__ import annotations

import base64
import json
import logging
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def publisher_mock(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    mock = MagicMock()
    mock.publish_post_event.return_value = "pubsub-msg-post"
    mock.publish_comment_event.return_value = "pubsub-msg-comment"
    mock.publish_reaction_event.return_value = "pubsub-msg-reaction"
    mock.publish_bookmark_event.return_value = "pubsub-msg-bookmark"
    monkeypatch.setattr("app.main.publisher", mock)
    return mock


@pytest.fixture
def client(publisher_mock: MagicMock) -> TestClient:
    from app.main import app

    return TestClient(app)


def test_post_create_202_and_envelope(client: TestClient, publisher_mock: MagicMock) -> None:
    body = {
        "title": "標題",
        "content": "原文",
        "language": "zh",
        "author_id": "m1",
        "topic_id": "t1",
        "ip": "203.0.113.1",
        "spamScore": 0.12,
        "poll": {
            "title": "票選",
            "options": [{"text": "A"}, {"text": "B"}],
        },
    }
    res = client.post("/post/create", json=body)
    assert res.status_code == 202
    assert res.json() == {"message_id": "pubsub-msg-post"}
    publisher_mock.publish_post_event.assert_called_once()
    env = publisher_mock.publish_post_event.call_args[0][0]
    assert env["entity"] == "post"
    assert env["operation"] == "create"
    assert env["data"]["title"] == "標題"
    assert env["data"]["content"] == "原文"
    assert env["data"]["author_id"] == "m1"
    assert env["data"]["topic_id"] == "t1"
    assert env["data"]["ip"] == "203.0.113.1"
    assert env["data"]["spam_score"] == pytest.approx(0.12)
    assert env["data"]["poll"]["title"] == "票選"
    assert len(env["data"]["poll"]["options"]) == 2
    assert "occurred_at" in env


def test_post_create_rejects_without_title(client: TestClient, publisher_mock: MagicMock) -> None:
    res = client.post("/post/create", json={"content": "only content"})
    assert res.status_code == 422
    publisher_mock.publish_post_event.assert_not_called()


def test_reaction_invalid_emotion_422(client: TestClient, publisher_mock: MagicMock) -> None:
    res = client.post(
        "/reaction/create",
        json={"member_id": "m1", "post_id": "p1", "emotion": "invalid"},
    )
    assert res.status_code == 422
    publisher_mock.publish_reaction_event.assert_not_called()


def test_post_update_202_operation_update(client: TestClient, publisher_mock: MagicMock) -> None:
    res = client.post(
        "/post/update",
        json={"id": "p1", "title": "t", "status": "draft"},
    )
    assert res.status_code == 202
    env = publisher_mock.publish_post_event.call_args[0][0]
    assert env["operation"] == "update"
    assert env["data"]["id"] == "p1"
    assert env["data"]["status"] == "draft"


def test_comment_create_202(client: TestClient, publisher_mock: MagicMock) -> None:
    res = client.post(
        "/comment/create",
        json={
            "member_id": "m1",
            "post_id": "p1",
            "content": "hello",
            "status": "pending",
        },
    )
    assert res.status_code == 202
    assert res.json() == {"message_id": "pubsub-msg-comment"}
    env = publisher_mock.publish_comment_event.call_args[0][0]
    assert env["entity"] == "comment"
    assert env["operation"] == "create"
    assert env["data"]["content"] == "hello"
    assert env["data"]["status"] == "pending"


def test_reaction_create_202(client: TestClient, publisher_mock: MagicMock) -> None:
    res = client.post(
        "/reaction/create",
        json={"member_id": "m1", "post_id": "p1", "emotion": "happy"},
    )
    assert res.status_code == 202
    env = publisher_mock.publish_reaction_event.call_args[0][0]
    assert env["entity"] == "reaction"
    assert env["data"]["emotion"] == "happy"


def test_bookmark_create_202(client: TestClient, publisher_mock: MagicMock) -> None:
    res = client.post(
        "/bookmark/create",
        json={"member_id": "m1", "post_id": "p1"},
    )
    assert res.status_code == 202
    assert res.json() == {"message_id": "pubsub-msg-bookmark"}
    env = publisher_mock.publish_bookmark_event.call_args[0][0]
    assert env["entity"] == "bookmark"
    assert env["operation"] == "create"
    assert env["data"]["post_id"] == "p1"
    assert env["data"]["member_id"] == "m1"


def test_bookmark_update_202(client: TestClient, publisher_mock: MagicMock) -> None:
    res = client.post(
        "/bookmark/update",
        json={"id": "b1", "member_id": "m1", "post_id": "p2"},
    )
    assert res.status_code == 202
    env = publisher_mock.publish_bookmark_event.call_args[0][0]
    assert env["operation"] == "update"
    assert env["data"]["id"] == "b1"


def test_bookmark_missing_post_id_422(client: TestClient, publisher_mock: MagicMock) -> None:
    res = client.post("/bookmark/create", json={"member_id": "m1"})
    assert res.status_code == 422
    publisher_mock.publish_bookmark_event.assert_not_called()


def test_hooks_sync_translations_forwards_source_status(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    called: dict = {}

    def fake_sync(*, article_type, item_id, source_text, source_title, source_status):
        called["article_type"] = article_type
        called["item_id"] = item_id
        called["source_text"] = source_text
        called["source_title"] = source_title
        called["source_status"] = source_status
        return {"ok": True}

    monkeypatch.setattr("app.main.sync_translations_from_hook", fake_sync)

    res = client.post(
        "/hooks/sync-translations",
        json={
            "type": "post",
            "id": "p1",
            "source_text": "body",
            "source_title": "title",
            "status": "pending",
        },
    )

    assert res.status_code == 200
    assert res.json() == {"ok": True}
    assert called == {
        "article_type": "post",
        "item_id": "p1",
        "source_text": "body",
        "source_title": "title",
        "source_status": "pending",
    }


def test_hooks_sync_translations_logs_value_error_context(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(
        "app.main.sync_translations_from_hook",
        MagicMock(side_effect=ValueError("post id=p1 不存在")),
    )

    with caplog.at_level(logging.WARNING, logger="app.main"):
        res = client.post(
            "/hooks/sync-translations",
            json={
                "type": "post",
                "id": "p1",
                "source_text": "body",
                "source_title": "title",
            },
        )

    assert res.status_code == 400
    log_messages = [record.getMessage() for record in caplog.records]
    assert any(
        '"event": "hooks_sync_translations_bad_request"' in message
        and '"article_type": "post"' in message
        and '"item_id": "p1"' in message
        and '"error": "post id=p1 不存在"' in message
        and '"has_source_text": true' in message
        and '"has_source_title": true' in message
        and '"status_code": 400' in message
        for message in log_messages
    )


def test_translation_push_acks_gemini_malformed_json(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "app.main.handle_translation_pubsub_payload",
        MagicMock(
            side_effect=RuntimeError(
                "Gemini 回傳非合法 JSON: Expecting ',' delimiter"
            )
        ),
    )
    payload = {
        "type": "post",
        "id": "72",
        "source_text": "body",
        "source_title": "title",
    }
    encoded = base64.b64encode(
        json.dumps(payload, ensure_ascii=False).encode("utf-8")
    ).decode("ascii")

    res = client.post("/pubsub/push/translation", json={"message": {"data": encoded}})

    assert res.status_code == 200
    assert res.json() == {}


def test_translation_push_acks_keystone_update_access_denied(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "app.main.handle_translation_pubsub_payload",
        MagicMock(
            side_effect=RuntimeError(
                "GraphQL error: [{'message': 'Access denied: You cannot update that "
                "Post - it may not exist', 'extensions': {'code': 'KS_ACCESS_DENIED'}}]"
            )
        ),
    )
    payload = {
        "type": "post",
        "id": "122",
        "source_text": "body",
        "source_title": "title",
    }
    encoded = base64.b64encode(
        json.dumps(payload, ensure_ascii=False).encode("utf-8")
    ).decode("ascii")

    res = client.post("/pubsub/push/translation", json={"message": {"data": encoded}})

    assert res.status_code == 200
    assert res.json() == {}
