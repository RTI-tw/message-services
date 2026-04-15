"""
翻譯 job 處理邏輯已移至 `app.translation_job`（API 映像僅含 app/）。
此模組保留 re-export，供舊程式與測試以 `subscriber.translation_handler` 匯入。
"""

from app.translation_job import handle_translation_pubsub_payload

__all__ = ["handle_translation_pubsub_payload"]
