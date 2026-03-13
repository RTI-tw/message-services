from typing import Any, Dict, Optional

import httpx

from .config import get_settings


class KeystoneGQLClient:
    def __init__(self) -> None:
        self._settings = get_settings()
        if not self._settings.keystone_gql_endpoint:
            raise RuntimeError("KEYSTONE_GQL_ENDPOINT 環境變數未設定")

        headers = {"Content-Type": "application/json"}
        if self._settings.keystone_auth_token:
            headers["Authorization"] = f"Bearer {self._settings.keystone_auth_token}"

        self._client = httpx.Client(base_url=self._settings.keystone_gql_endpoint, headers=headers, timeout=10.0)

    def execute(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        resp = self._client.post("", json={"query": query, "variables": variables or {}})
        resp.raise_for_status()
        data = resp.json()
        if "errors" in data:
            raise RuntimeError(f"GraphQL error: {data['errors']}")
        return data["data"]


gql_client = KeystoneGQLClient()

