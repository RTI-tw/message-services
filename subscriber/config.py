import os
from functools import lru_cache


class SubscriberSettings:
    def __init__(self) -> None:
        # GCP
        self.gcp_project_id: str = os.getenv("GCP_PROJECT_ID", "")

        # Pub/Sub subscriptions（每個 resource 各一個）
        # 建議一個 topic 對應一個 subscription
        self.sub_post: str = os.getenv("PUBSUB_SUB_POST", "forum-post-events-sub")
        self.sub_comment: str = os.getenv("PUBSUB_SUB_COMMENT", "forum-comment-events-sub")
        self.sub_reaction: str = os.getenv("PUBSUB_SUB_REACTION", "forum-reaction-events-sub")

        # Keystone GraphQL
        # 例如：https://forum-cms.example.com/api/graphql
        self.keystone_gql_endpoint: str = os.getenv("KEYSTONE_GQL_ENDPOINT", "")
        # 若需要 auth，可放 Bearer token 或自訂 header 值
        self.keystone_auth_token: str = os.getenv("KEYSTONE_AUTH_TOKEN", "")


@lru_cache
def get_settings() -> SubscriberSettings:
    return SubscriberSettings()

