import os
from typing import Any, Dict, Optional

import httpx

from .gcp_auth import invoker_auth_headers


_client: Optional[httpx.Client] = None

# 明確保留 keep-alive 連線，與 httpx 預設行為一致但上限可調
_DEFAULT_LIMITS = httpx.Limits(max_keepalive_connections=20, max_connections=100)


def _get_client() -> httpx.Client:
    global _client
    endpoint = (os.getenv("KEYSTONE_GQL_ENDPOINT") or "").strip()
    if not endpoint:
        raise RuntimeError("KEYSTONE_GQL_ENDPOINT 環境變數未設定")

    if _client is None:
        headers = {"Content-Type": "application/json"}
        token = (os.getenv("KEYSTONE_AUTH_TOKEN") or "").strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        _client = httpx.Client(
            base_url=endpoint,
            headers=headers,
            timeout=60.0,
            limits=_DEFAULT_LIMITS,
        )
    return _client


def execute_gql(query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    client = _get_client()
    # Per-request so the (cached) Google ID token can refresh on expiry. Sent as
    # X-Serverless-Authorization to authenticate to the locked GQL Cloud Run service.
    endpoint = (os.getenv("KEYSTONE_GQL_ENDPOINT") or "").strip()
    resp = client.post(
        "",
        json={"query": query, "variables": variables or {}},
        headers=invoker_auth_headers(endpoint),
    )
    resp.raise_for_status()
    payload = resp.json()
    if "errors" in payload:
        raise RuntimeError(f"GraphQL error: {payload['errors']}")
    return payload["data"]
