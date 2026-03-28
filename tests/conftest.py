"""測試前設定必要環境變數，避免載入 app 時 PubSubPublisher 初始化失敗。"""

from __future__ import annotations

import os

os.environ.setdefault("GCP_PROJECT_ID", "test-project")
