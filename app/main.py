import asyncio
import base64
import json
import logging
import os
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from pydantic import ValidationError

from . import schemas
from .gemini_translate import translate_and_detect
from .hooks_translate import sync_translations_from_hook
from .pubsub_client import publisher

logger = logging.getLogger(__name__)
app = FastAPI(title="Forum Message Services", version="0.1.0")


def verify_hook_secret(x_hook_secret: Annotated[str | None, Header()] = None) -> None:
    expected = (os.getenv("KEYSTONE_HOOK_SECRET") or "").strip()
    if not expected:
        return
    if not x_hook_secret or x_hook_secret != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing X-Hook-Secret")


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


@app.post("/hooks/sync-translations")
async def keystone_hook_sync_translations(
    body: schemas.KeystoneHookSyncTranslationRequest,
    _auth: Annotated[None, Depends(verify_hook_secret)],
):
    """
    供 Keystone hooks 呼叫：依 Post / Comment 的 `content`（原文）翻譯後，
    以 GQL 更新 `language` 與各語系 `contentZh` / `contentEn` / `contentVi` / `contentTh` / `contentId`。
    若環境變數 `KEYSTONE_HOOK_SECRET` 有設定，請帶 header `X-Hook-Secret`。
    """
    try:
        return await asyncio.to_thread(
            sync_translations_from_hook,
            article_type=body.article_type,
            item_id=body.id,
            source_text=body.source_text,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001
        logger.exception("hooks/sync-translations failed: %s", e)
        raise HTTPException(status_code=502, detail=str(e)) from e


@app.post("/translate")
async def translate_article(body: schemas.TranslateRequest):
    """
    使用 Gemini 偵測語言並翻譯為 zh-tw / en / vi / th / id（JSON 結構與 prompt 約定一致）。
    """
    try:
        raw = await asyncio.to_thread(translate_and_detect, body.text.strip())
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001
        logger.exception("Gemini translate failed: %s", e)
        raise HTTPException(status_code=502, detail=str(e)) from e

    try:
        parsed = schemas.GeminiTranslateResponse.model_validate(raw)
    except ValidationError as e:
        raise HTTPException(
            status_code=502,
            detail={"message": "Gemini 回傳格式不符合預期", "errors": e.errors(), "raw": raw},
        ) from e

    return parsed.model_dump(mode="json", by_alias=True)

