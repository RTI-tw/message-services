import os
from functools import lru_cache


class Settings:
    def __init__(self) -> None:
        self.gcp_project_id: str = os.getenv("GCP_PROJECT_ID", "")
        # 個別 topic，讓下游可以分流處理
        self.post_topic: str = os.getenv("PUBSUB_TOPIC_POST", "forum-post-events")
        self.comment_topic: str = os.getenv("PUBSUB_TOPIC_COMMENT", "forum-comment-events")
        self.reaction_topic: str = os.getenv("PUBSUB_TOPIC_REACTION", "forum-reaction-events")
        self.bookmark_topic: str = os.getenv("PUBSUB_TOPIC_BOOKMARK", "forum-bookmark-events")
        # Gemini（文章翻譯）
        self.gemini_api_key: str = (os.getenv("GEMINI_API_KEY") or "").strip()
        _gemini_model = (os.getenv("GEMINI_MODEL") or "").strip()
        self.gemini_model: str = _gemini_model or "gemini-1.5-flash"


@lru_cache
def get_settings() -> Settings:
    return Settings()

