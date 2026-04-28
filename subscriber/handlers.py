from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from .gql_client import gql_client


def _split_envelope(payload: Dict[str, Any]) -> Tuple[str, str, Dict[str, Any]]:
    entity = payload.get("entity")
    operation = payload.get("operation")
    data = payload.get("data") or {}
    if not entity or not operation:
        raise ValueError(f"invalid event envelope: {payload}")
    return str(entity), str(operation), data


def _coerce_post_status_for_create(data: Dict[str, Any]) -> str:
    """建立 Post 時的 status；未傳時預設 published；相容 is_active。"""
    s = data.get("status")
    if s is not None and str(s).strip():
        return str(s).strip()
    ia = data.get("is_active")
    if ia is False:
        return "draft"
    if ia is True:
        return "published"
    return "published"


def _optional_post_status_for_update(data: Dict[str, Any]) -> Optional[str]:
    """僅在 payload 明確帶 status / is_active 時才更新，避免部分更新誤改狀態。"""
    if "status" in data and data["status"] is not None and str(data["status"]).strip():
        return str(data["status"]).strip()
    if "is_active" in data:
        if data["is_active"] is False:
            return "draft"
        if data["is_active"] is True:
            return "published"
    return None


def _scalar_datetime(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    s = str(value).strip()
    return s or None


def _poll_create_payload(poll: Dict[str, Any]) -> Dict[str, Any]:
    """PollCreateInput：title、選填 expiresAt、選項 options.create。"""
    title = (poll.get("title") or "").strip()
    if not title:
        raise ValueError("poll.title 為必填")
    out: Dict[str, Any] = {"title": title}
    exp = poll.get("expires_at")
    if exp is None:
        exp = poll.get("expiresAt")
    exp_iso = _scalar_datetime(exp)
    if exp_iso:
        out["expiresAt"] = exp_iso
    opts = poll.get("options") or []
    creates: List[Dict[str, str]] = []
    for o in opts:
        if not isinstance(o, dict):
            continue
        t = (o.get("text") or "").strip()
        if t:
            creates.append({"text": t})
    if creates:
        out["options"] = {"create": creates}
    return out


def _append_nested_poll(
    result: Dict[str, Any],
    poll: Optional[Dict[str, Any]],
    *,
    is_update: bool,
) -> None:
    if not poll or not isinstance(poll, dict):
        return
    pid = (poll.get("id") or "").strip()
    if is_update and pid:
        inner: Dict[str, Any] = {}
        if poll.get("title") is not None:
            inner["title"] = str(poll["title"]).strip()
        exp = poll.get("expires_at")
        if exp is None:
            exp = poll.get("expiresAt")
        exp_iso = _scalar_datetime(exp)
        if exp_iso is not None:
            inner["expiresAt"] = exp_iso
        if inner:
            result["poll"] = {"update": {"where": {"id": pid}, "data": inner}}
        return
    if not is_update:
        result["poll"] = {"create": _poll_create_payload(poll)}
        return
    # update 但未帶 poll id：無法安全巢狀 create（可能已有一對一 poll），略過
    return


def _post_input_from_event(data: Dict[str, Any], *, is_update: bool) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key in [
        "title",
        "content",
        "language",
        "title_zh",
        "title_en",
        "title_vi",
        "title_id",
        "title_th",
        "content_zh",
        "content_en",
        "content_vi",
        "content_id",
        "content_th",
        "ip",
    ]:
        if key in data and data[key] is not None:
            result[key] = data[key]

    if "violationScore" in data and data["violationScore"] is not None:
        result["spamScore"] = data["violationScore"]
    elif "violation_score" in data and data["violation_score"] is not None:
        result["spamScore"] = data["violation_score"]
    elif "spamScore" in data and data["spamScore"] is not None:
        result["spamScore"] = data["spamScore"]
    elif "spam_score" in data and data["spam_score"] is not None:
        result["spamScore"] = data["spam_score"]

    if is_update:
        st = _optional_post_status_for_update(data)
        if st is not None:
            result["status"] = st
    else:
        result["status"] = _coerce_post_status_for_create(data)

    author_id = data.get("author_id")
    if author_id:
        result["author"] = {"connect": {"id": author_id}}

    topic_id = data.get("topic_id")
    if topic_id:
        result["topic"] = {"connect": {"id": topic_id}}

    hero_id = data.get("hero_image_id") or data.get("heroImageId")
    if hero_id:
        result["heroImage"] = {"connect": {"id": hero_id}}

    _append_nested_poll(result, data.get("poll"), is_update=is_update)

    return result


def _comment_input_from_event(data: Dict[str, Any]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key in [
        "content",
        "content_zh",
        "content_en",
        "content_vi",
        "content_id",
        "content_th",
        "state",
        "status",
        "published_date",
        "is_edited",
        "is_active",
    ]:
        if key in data and data[key] is not None:
            result[key] = data[key]

    member_id = data.get("member_id")
    if member_id:
        result["member"] = {"connect": {"id": member_id}}

    post_id = data.get("post_id")
    if post_id:
        result["post"] = {"connect": {"id": post_id}}

    parent_id = data.get("parent_id")
    if parent_id:
        result["parent"] = {"connect": {"id": parent_id}}

    root_id = data.get("root_id")
    if root_id:
        result["root"] = {"connect": {"id": root_id}}

    return result


def _reaction_input_from_event(data: Dict[str, Any]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    # emotion, createdAt
    if "emotion" in data and data["emotion"] is not None:
        result["emotion"] = data["emotion"]
    if "created_at" in data and data["created_at"] is not None:
        result["createdAt"] = data["created_at"]

    member_id = data.get("member_id")
    if member_id:
        result["member"] = {"connect": {"id": member_id}}

    post_id = data.get("post_id")
    if post_id:
        result["post"] = {"connect": {"id": post_id}}

    comment_id = data.get("comment_id")
    if comment_id:
        result["comment"] = {"connect": {"id": comment_id}}

    return result


def _bookmark_input_from_event(data: Dict[str, Any]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    post_id = data.get("post_id")
    if post_id:
        result["post"] = {"connect": {"id": post_id}}
    member_id = data.get("member_id")
    if member_id:
        result["member"] = {"connect": {"id": member_id}}
    return result


def handle_event(payload: Dict[str, Any]) -> None:
    """
    根據 entity/operation 轉成對 Keystone 的 GQL mutation。
    """

    entity, operation, data = _split_envelope(payload)

    if entity == "post":
        _handle_post(operation, data)
    elif entity == "comment":
        _handle_comment(operation, data)
    elif entity == "reaction":
        _handle_reaction(operation, data)
    elif entity == "bookmark":
        _handle_bookmark(operation, data)
    else:
        raise ValueError(f"unsupported entity: {entity}")


def _handle_post(operation: str, data: Dict[str, Any]) -> None:
    is_update = operation == "update"
    gql_data = _post_input_from_event(data, is_update=is_update)
    if operation == "create":
        mutation = """
          mutation CreatePost($data: PostCreateInput!) {
            createPost(data: $data) { id }
          }
        """
        gql_client.execute(mutation, {"data": gql_data})
    elif operation == "update":
        post_id = data.get("id")
        if not post_id:
            raise ValueError("update post event requires 'id'")
        mutation = """
          mutation UpdatePost($id: ID!, $data: PostUpdateInput!) {
            updatePost(where: { id: $id }, data: $data) { id }
          }
        """
        gql_client.execute(mutation, {"id": post_id, "data": gql_data})
    else:
        raise ValueError(f"unsupported operation for post: {operation}")


def _handle_comment(operation: str, data: Dict[str, Any]) -> None:
    gql_data = _comment_input_from_event(data)
    if operation == "create":
        mutation = """
          mutation CreateComment($data: CommentCreateInput!) {
            createComment(data: $data) { id }
          }
        """
        gql_client.execute(mutation, {"data": gql_data})
    elif operation == "update":
        comment_id = data.get("id")
        if not comment_id:
            raise ValueError("update comment event requires 'id'")
        mutation = """
          mutation UpdateComment($id: ID!, $data: CommentUpdateInput!) {
            updateComment(where: { id: $id }, data: $data) { id }
          }
        """
        gql_client.execute(mutation, {"id": comment_id, "data": gql_data})
    else:
        raise ValueError(f"unsupported operation for comment: {operation}")


def _handle_reaction(operation: str, data: Dict[str, Any]) -> None:
    gql_data = _reaction_input_from_event(data)
    if operation == "create":
        mutation = """
          mutation CreateReaction($data: ReactionCreateInput!) {
            createReaction(data: $data) { id }
          }
        """
        gql_client.execute(mutation, {"data": gql_data})
    elif operation == "update":
        reaction_id = data.get("id")
        if not reaction_id:
            raise ValueError("update reaction event requires 'id'")
        mutation = """
          mutation UpdateReaction($id: ID!, $data: ReactionUpdateInput!) {
            updateReaction(where: { id: $id }, data: $data) { id }
          }
        """
        gql_client.execute(mutation, {"id": reaction_id, "data": gql_data})
    else:
        raise ValueError(f"unsupported operation for reaction: {operation}")


def _handle_bookmark(operation: str, data: Dict[str, Any]) -> None:
    gql_data = _bookmark_input_from_event(data)
    if operation == "create":
        mutation = """
          mutation CreateBookmark($data: BookmarkCreateInput!) {
            createBookmark(data: $data) { id }
          }
        """
        gql_client.execute(mutation, {"data": gql_data})
    elif operation == "update":
        bookmark_id = data.get("id")
        if not bookmark_id:
            raise ValueError("update bookmark event requires 'id'")
        mutation = """
          mutation UpdateBookmark($id: ID!, $data: BookmarkUpdateInput!) {
            updateBookmark(where: { id: $id }, data: $data) { id }
          }
        """
        gql_client.execute(mutation, {"id": bookmark_id, "data": gql_data})
    else:
        raise ValueError(f"unsupported operation for bookmark: {operation}")
