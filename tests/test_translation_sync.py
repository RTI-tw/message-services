"""測試 Post／Content 合併翻譯與 Gemini 合併回傳解析。"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


def _fake_gemini_merged_payload() -> dict:
    return {
        "title": {
            "detect-lang": "zh-tw",
            "translation": {
                "zh-tw": "標",
                "en": "T",
                "vi": "T",
                "th": "T",
                "id": "T",
            },
        },
        "content": {
            "detect-lang": "en",
            "translation": {
                "zh-tw": "內",
                "en": "Body",
                "vi": "B",
                "th": "B",
                "id": "B",
            },
            "spamScore": 0.42,
        },
    }


def test_translate_title_and_content_merged_rejects_empty_title() -> None:
    from app.gemini_translate import translate_title_and_content_merged

    with pytest.raises(ValueError, match="皆非空"):
        translate_title_and_content_merged("", "body", include_spam_for_body=True)


def test_translate_title_and_content_merged_rejects_empty_body() -> None:
    from app.gemini_translate import translate_title_and_content_merged

    with pytest.raises(ValueError, match="皆非空"):
        translate_title_and_content_merged("title", "", include_spam_for_body=False)


def test_translate_title_and_content_merged_uses_single_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app import gemini_translate as gt

    calls: list[tuple[str, str]] = []

    def fake_call(system: str, user: str) -> dict:
        calls.append((system[:40], user[:20]))
        return _fake_gemini_merged_payload()

    monkeypatch.setattr(gt, "_call_gemini_json", fake_call)

    out = gt.translate_title_and_content_merged(
        "標題",
        "正文",
        include_spam_for_body=True,
    )
    assert len(calls) == 1
    assert out["title"]["detect-lang"] == "zh-tw"
    assert out["content"]["spamScore"] == 0.42
    assert isinstance(out["title"]["translation"], dict)
    assert isinstance(out["content"]["translation"], dict)


def test_translate_title_and_content_merged_rejects_malformed_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app import gemini_translate as gt

    def fake_call(_system: str, _user: str) -> dict:
        return {"title": {"translation": {}}, "content": "not-a-dict"}

    monkeypatch.setattr(gt, "_call_gemini_json", fake_call)

    with pytest.raises(RuntimeError, match="content"):
        gt.translate_title_and_content_merged("a", "b", include_spam_for_body=False)


def test_sync_post_or_content_calls_merged_once_when_title_and_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.hooks_translate import _sync_post_or_content_translations

    merged_n = 0
    detect_n = 0

    def fake_merged(title: str, content: str, *, include_spam_for_body: bool) -> dict:
        nonlocal merged_n
        merged_n += 1
        assert include_spam_for_body is True
        assert title == "標"
        assert content == "文"
        return _fake_gemini_merged_payload()

    def fake_detect(_text: str) -> dict:
        nonlocal detect_n
        detect_n += 1
        raise AssertionError("translate_and_detect should not be used when both exist")

    monkeypatch.setattr(
        "app.hooks_translate.translate_title_and_content_merged",
        fake_merged,
    )
    monkeypatch.setattr(
        "app.hooks_translate.translate_and_detect",
        fake_detect,
    )

    data = _sync_post_or_content_translations(
        "post",
        "post-id-1",
        "文",
        "標",
    )
    assert merged_n == 1
    assert detect_n == 0
    assert "content_zh" in data
    assert "title_zh" in data
    assert data["spamScore"] == pytest.approx(0.42)
    assert data["language"] == "en"


def test_sync_post_or_content_calls_detect_only_when_content_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.hooks_translate import _sync_post_or_content_translations

    merged_n = 0
    detect_n = 0

    def fake_execute_gql(query: str, _variables: dict) -> dict:
        assert "post(" in query
        return {
            "post": {
                "title": "",
                "content": "只有正文",
                "language": "zh",
            }
        }

    def fake_merged(*_a, **_kw) -> dict:
        nonlocal merged_n
        merged_n += 1
        return _fake_gemini_merged_payload()

    def fake_detect(text: str) -> dict:
        nonlocal detect_n
        detect_n += 1
        return {
            "detect-lang": "zh-tw",
            "translation": {
                "zh-tw": "原文",
                "en": "en",
                "vi": "vi",
                "th": "th",
                "id": "id",
            },
        }

    monkeypatch.setattr("app.hooks_translate.execute_gql", fake_execute_gql)
    monkeypatch.setattr(
        "app.hooks_translate.translate_title_and_content_merged",
        fake_merged,
    )
    monkeypatch.setattr(
        "app.hooks_translate.translate_and_detect",
        fake_detect,
    )

    data = _sync_post_or_content_translations(
        "post",
        "post-id-2",
        "只有正文",
        None,
    )
    assert merged_n == 0
    assert detect_n == 1
    assert "content_zh" in data
    assert "title_zh" not in data


def test_sync_post_or_content_calls_detect_only_when_title_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.hooks_translate import _sync_post_or_content_translations

    merged_n = 0
    detect_n = 0

    def fake_execute_gql(query: str, _variables: dict) -> dict:
        assert "content(" in query
        return {
            "content": {
                "title": "只有標題",
                "content": "",
                "language": "zh",
            }
        }

    def fake_merged(*_a, **_kw) -> dict:
        nonlocal merged_n
        merged_n += 1
        return _fake_gemini_merged_payload()

    def fake_detect(text: str) -> dict:
        nonlocal detect_n
        detect_n += 1
        return {
            "detect-lang": "zh-tw",
            "translation": {
                "zh-tw": "標",
                "en": "T",
                "vi": "T",
                "th": "T",
                "id": "T",
            },
        }

    monkeypatch.setattr("app.hooks_translate.execute_gql", fake_execute_gql)
    monkeypatch.setattr(
        "app.hooks_translate.translate_title_and_content_merged",
        fake_merged,
    )
    monkeypatch.setattr(
        "app.hooks_translate.translate_and_detect",
        fake_detect,
    )

    data = _sync_post_or_content_translations(
        "content",
        "c-id-1",
        None,
        "只有標題",
    )
    assert merged_n == 0
    assert detect_n == 1
    assert "title_zh" in data
    assert "content_zh" not in data


def test_sync_post_or_content_content_entity_no_spam_in_merge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """content 靜態頁合併時應要求 include_spam_for_body=False。"""
    from app.hooks_translate import _sync_post_or_content_translations

    seen: dict[str, bool] = {}

    def fake_merged(title: str, content: str, *, include_spam_for_body: bool) -> dict:
        seen["spam"] = include_spam_for_body
        return _fake_gemini_merged_payload()

    monkeypatch.setattr(
        "app.hooks_translate.translate_title_and_content_merged",
        fake_merged,
    )
    monkeypatch.setattr(
        "app.hooks_translate.translate_and_detect",
        MagicMock(side_effect=AssertionError),
    )

    _sync_post_or_content_translations("content", "x", "body", "title")
    assert seen.get("spam") is False
