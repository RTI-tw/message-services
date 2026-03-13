from fastapi import Depends, FastAPI, HTTPException, status

from . import schemas
from .pubsub_client import publisher

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


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}

