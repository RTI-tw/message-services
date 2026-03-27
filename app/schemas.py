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

