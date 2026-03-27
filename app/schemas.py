from datetime import datetime
from enum import Enum
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class Operation(str, Enum):
    create = "create"
    update = "update"


class Post(BaseModel):
    id: Optional[str] = Field(default=None, description="CMS 端的 Post ID")
    title: str
    content_zh: Optional[str] = None
    content_en: Optional[str] = None
    content_vi: Optional[str] = None
    content_id: Optional[str] = None
    content_th: Optional[str] = None
    author_id: Optional[str] = Field(default=None, description="Member ID")
    is_active: Optional[bool] = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class CommentState(str, Enum):
    public = "public"
    private = "private"
    friend = "friend"


class Comment(BaseModel):
    id: Optional[str] = None
    member_id: Optional[str] = None
    post_id: Optional[str] = None
    content: Optional[str] = None
    content_zh: Optional[str] = None
    content_en: Optional[str] = None
    content_vi: Optional[str] = None
    content_id: Optional[str] = None
    content_th: Optional[str] = None
    parent_id: Optional[str] = None
    root_id: Optional[str] = None
    state: Optional[CommentState] = CommentState.public
    published_date: Optional[datetime] = None
    is_edited: Optional[bool] = False
    is_active: Optional[bool] = True


class Emotion(str, Enum):
    happy = "happy"
    angry = "angry"
    surprise = "surprise"
    sad = "sad"


class Reaction(BaseModel):
    id: Optional[str] = None
    member_id: Optional[str] = None
    post_id: Optional[str] = None
    comment_id: Optional[str] = None
    emotion: Emotion
    created_at: Optional[datetime] = None


class EventEnvelope(BaseModel):
    operation: Operation
    entity: str
    data: Dict[str, Any]
    occurred_at: datetime = Field(default_factory=datetime.utcnow)


class TranslateRequest(BaseModel):
    text: str = Field(min_length=1, description="要翻譯的原文")


class TranslationFiveLang(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    zh_tw: str = Field(validation_alias="zh-tw", serialization_alias="zh-tw")
    en: str
    vi: str
    th: str
    id_lang: str = Field(validation_alias="id", serialization_alias="id")


class GeminiTranslateResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    detect_lang: str = Field(
        validation_alias="detect-lang",
        serialization_alias="detect-lang",
    )
    translation: TranslationFiveLang
    spamScore: Optional[float] = None


class KeystoneHookSyncTranslationRequest(BaseModel):
    """Keystone hooks 呼叫：JSON 使用欄位名 `type`。"""

    model_config = ConfigDict(populate_by_name=True)

    article_type: Literal[
        "post",
        "comment",
        "topic",
        "poll",
        "pollOption",
        "content",
    ] = Field(
        validation_alias="type",
        serialization_alias="type",
    )
    id: str = Field(min_length=1, description="Keystone 實體 id")
    source_text: Optional[str] = Field(
        default=None,
        description="選填；若省略則由 GQL 讀取該筆原文欄位再翻譯",
    )
    source_title: Optional[str] = Field(
        default=None,
        description="Post 專用選填；若省略則由 GQL 讀取該筆 title 再翻譯",
    )


class ExportContentsToGcsRequest(BaseModel):
    prefix: str = Field(default="exports/contents", description="GCS 物件路徑前綴")
    page_size: int = Field(default=200, ge=1, le=1000, description="每次 GQL 擷取筆數")
    id: Optional[str] = Field(
        default=None,
        description="選填；若提供則只匯出指定 content id，未提供則匯出全部",
    )


class ExportTopicPostsToGcsRequest(BaseModel):
    prefix: str = Field(default="exports/topic-posts", description="GCS 物件路徑前綴")
    per_topic_limit: int = Field(default=10, ge=1, le=200, description="每個 topic 取幾筆")
    post_state: str = Field(
        default="active",
        description="文章狀態；active 會映射為 Keystone status=published",
    )
    scan_multiplier: int = Field(
        default=10,
        ge=1,
        le=50,
        description="為了計算熱門/含投票，先抓 per_topic_limit * scan_multiplier 筆再排序過濾",
    )

