import os
from functools import lru_cache


class Settings:
    def __init__(self) -> None:
        self.gcp_project_id: str = os.getenv("GCP_PROJECT_ID", "")
        # 個別 topic，讓下游可以分流處理
        self.post_topic: str = os.getenv("PUBSUB_TOPIC_POST", "forum-post-events")
        self.comment_topic: str = os.getenv("PUBSUB_TOPIC_COMMENT", "forum-comment-events")
        self.reaction_topic: str = os.getenv("PUBSUB_TOPIC_REACTION", "forum-reaction-events")


@lru_cache
def get_settings() -> Settings:
    return Settings()

