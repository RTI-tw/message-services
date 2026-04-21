from __future__ import annotations

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
