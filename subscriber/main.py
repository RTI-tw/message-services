import json
import logging
from concurrent.futures import TimeoutError
from typing import Callable, cast

from google.cloud import pubsub_v1

from .config import get_settings
from .handlers import handle_event
from .translation_handler import handle_translation_pubsub_payload

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("subscriber")


def _build_subscription_path(subscriber: pubsub_v1.SubscriberClient, subscription_name: str, project_id: str) -> str:
    if subscription_name.startswith("projects/"):
        return subscription_name
    return subscriber.subscription_path(project_id, subscription_name)


def main() -> None:
    settings = get_settings()
    if not settings.gcp_project_id:
        raise RuntimeError("GCP_PROJECT_ID 環境變數未設定")

    subscriber = pubsub_v1.SubscriberClient()

    sub_names = {
        "post": settings.sub_post,
        "comment": settings.sub_comment,
        "reaction": settings.sub_reaction,
        "bookmark": settings.sub_bookmark,
    }

    streaming_futures = []

    for entity, sub_name in sub_names.items():
        subscription_path = _build_subscription_path(subscriber, sub_name, settings.gcp_project_id)
        logger.info("Starting subscriber for %s on %s", entity, subscription_path)

        def callback(message, *, entity_name: str = entity) -> None:  # type: ignore[override]
            try:
                payload = json.loads(message.data.decode("utf-8"))
                logger.info("Received %s message: %s", entity_name, payload)
                handle_event(payload)
                message.ack()
            except Exception as exc:  # noqa: BLE001
                logger.exception("Failed to handle %s message: %s", entity_name, exc)
                # 視情況可改成 nack() 讓訊息重送
                message.nack()

        future = subscriber.subscribe(subscription_path, callback=cast(Callable, callback))
        streaming_futures.append(future)

    if settings.sub_translation_sync:

        def translation_callback(message) -> None:
            try:
                payload = json.loads(message.data.decode("utf-8"))
                logger.info("Received translation_sync message: %s", payload)
                result = handle_translation_pubsub_payload(payload)
                logger.info("translation_sync done: %s", result)
                message.ack()
            except (json.JSONDecodeError, ValueError) as exc:
                logger.warning(
                    "translation_sync skipped (ack, no retry): %s", exc
                )
                message.ack()
            except Exception as exc:  # noqa: BLE001
                logger.exception("translation_sync failed (nack for retry): %s", exc)
                message.nack()

        sub_path = _build_subscription_path(
            subscriber, settings.sub_translation_sync, settings.gcp_project_id
        )
        logger.info(
            "Starting subscriber for translation_sync on %s", sub_path
        )
        tf = subscriber.subscribe(sub_path, callback=cast(Callable, translation_callback))
        streaming_futures.append(tf)

    logger.info("Listening for messages on all subscriptions... Press Ctrl+C to exit.")

    try:
        for future in streaming_futures:
            future.result()
    except KeyboardInterrupt:
        logger.info("Shutting down subscribers...")
        for future in streaming_futures:
            future.cancel()
    except TimeoutError:
        logger.warning("Streaming pull timed out.")


if __name__ == "__main__":
    main()

