import json
from typing import Any, Dict

from google.cloud import pubsub_v1

from .config import get_settings


class PubSubPublisher:
    def __init__(self) -> None:
        self._settings = get_settings()
        if not self._settings.gcp_project_id:
            raise RuntimeError("GCP_PROJECT_ID 環境變數未設定")
        self._client = pubsub_v1.PublisherClient()

    def _topic_path(self, raw_topic: str) -> str:
        if raw_topic.startswith("projects/"):
            return raw_topic
        return self._client.topic_path(self._settings.gcp_project_id, raw_topic)

    def publish(self, topic: str, message: Dict[str, Any]) -> str:
        data = json.dumps(message, ensure_ascii=False).encode("utf-8")
        future = self._client.publish(self._topic_path(topic), data)
        message_id = future.result()
        return message_id

    def publish_post_event(self, payload: Dict[str, Any]) -> str:
        return self.publish(self._settings.post_topic, payload)

    def publish_comment_event(self, payload: Dict[str, Any]) -> str:
        return self.publish(self._settings.comment_topic, payload)

    def publish_reaction_event(self, payload: Dict[str, Any]) -> str:
        return self.publish(self._settings.reaction_topic, payload)

    def publish_bookmark_event(self, payload: Dict[str, Any]) -> str:
        return self.publish(self._settings.bookmark_topic, payload)


publisher = PubSubPublisher()

