from __future__ import annotations

from typing import Any, Dict, Tuple

from .gql_client import gql_client


def _split_envelope(payload: Dict[str, Any]) -> Tuple[str, str, Dict[str, Any]]:
    entity = payload.get("entity")
    operation = payload.get("operation")
    data = payload.get("data") or {}
    if not entity or not operation:
        raise ValueError(f"invalid event envelope: {payload}")
    return str(entity), str(operation), data


def _post_input_from_event(data: Dict[str, Any]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    # 直接對應到 Post list 的欄位
    for key in [
        "title",
        "content_zh",
        "content_en",
        "content_vi",
        "content_id",
        "content_th",
        "is_active",
    ]:
        if key in data and data[key] is not None:
            result[key] = data[key]

    # author: relationship -> connect by id
    author_id = data.get("author_id")
    if author_id:
        result["author"] = {"connect": {"id": author_id}}

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
    else:
        raise ValueError(f"unsupported entity: {entity}")


def _handle_post(operation: str, data: Dict[str, Any]) -> None:
    gql_data = _post_input_from_event(data)
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

