import asyncio
import base64
import json
import logging

from fastapi import FastAPI, HTTPException, Request, status

from . import schemas
from .pubsub_client import publisher

logger = logging.getLogger(__name__)
app = FastAPI(title="Forum Message Services", version="0.1.0")


def build_envelope(entity: str, operation: schemas.Operation, payload) -> schemas.EventEnvelope:
    return schemas.EventEnvelope(
        entity=entity,
        operation=operation,
        data=payload.model_dump(mode="json"),
    )


@app.post("/post/create", status_code=status.HTTP_202_ACCEPTED)
async def create_post(post: schemas.Post):
    envelope = build_envelope("post", schemas.Operation.create, post)
    try:
        message_id = publisher.publish_post_event(envelope.model_dump(mode="json"))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"message_id": message_id}


@app.post("/post/update", status_code=status.HTTP_202_ACCEPTED)
async def update_post(post: schemas.Post):
    envelope = build_envelope("post", schemas.Operation.update, post)
    try:
        message_id = publisher.publish_post_event(envelope.model_dump(mode="json"))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"message_id": message_id}


@app.post("/comment/create", status_code=status.HTTP_202_ACCEPTED)
async def create_comment(comment: schemas.Comment):
    envelope = build_envelope("comment", schemas.Operation.create, comment)
    try:
        message_id = publisher.publish_comment_event(envelope.model_dump(mode="json"))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"message_id": message_id}


@app.post("/comment/update", status_code=status.HTTP_202_ACCEPTED)
async def update_comment(comment: schemas.Comment):
    envelope = build_envelope("comment", schemas.Operation.update, comment)
    try:
        message_id = publisher.publish_comment_event(envelope.model_dump(mode="json"))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"message_id": message_id}


@app.post("/reaction/create", status_code=status.HTTP_202_ACCEPTED)
async def create_reaction(reaction: schemas.Reaction):
    envelope = build_envelope("reaction", schemas.Operation.create, reaction)
    try:
        message_id = publisher.publish_reaction_event(envelope.model_dump(mode="json"))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"message_id": message_id}


@app.post("/reaction/update", status_code=status.HTTP_202_ACCEPTED)
async def update_reaction(reaction: schemas.Reaction):
    envelope = build_envelope("reaction", schemas.Operation.update, reaction)
    try:
        message_id = publisher.publish_reaction_event(envelope.model_dump(mode="json"))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"message_id": message_id}


@app.post("/pubsub/push")
async def pubsub_push(request: Request):
    """
    Pub/Sub Push 入口：收到訊息後解碼並轉交給 subscriber 寫入 Keystone。
    回傳 2xx 表示 ack，非 2xx 會讓 Pub/Sub 重送。
    """
    try:
        body = await request.json()
    except Exception as e:
        logger.warning("Invalid push body: %s", e)
        raise HTTPException(status_code=400, detail="Invalid JSON") from e

    message = body.get("message") if isinstance(body, dict) else None
    if not message or "data" not in message:
        logger.warning("Missing message.data in push body")
        raise HTTPException(status_code=400, detail="Missing message.data")

    try:
        raw = base64.b64decode(message["data"])
        payload = json.loads(raw.decode("utf-8"))
    except (ValueError, KeyError, json.JSONDecodeError) as e:
        logger.warning("Failed to decode push data: %s", e)
        raise HTTPException(status_code=400, detail="Invalid message.data") from e

    try:
        from subscriber.handlers import handle_event

        await asyncio.to_thread(handle_event, payload)
        return {}
    except Exception as e:
        logger.exception("handle_event failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}

