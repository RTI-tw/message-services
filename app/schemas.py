from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class Operation(str, Enum):
    create = "create"
    update = "update"


class PollOptionEmbedded(BaseModel):
    """Pub/Sub 內嵌於 post 的投票選項（對應 PollOption.text）。"""

    text: str = Field(min_length=1)


class PollEmbedded(BaseModel):
    """Pub/Sub 內嵌於 post 的投票；建立 Post 時一併巢狀建立 Poll / PollOption。"""

    model_config = ConfigDict(extra="ignore")

    id: Optional[str] = Field(
        default=None,
        description="選填；update 時若帶 CMS 的 poll id 可只更新該投票標題／截止時間",
    )
    title: str = Field(min_length=1, description="投票標題（原文）")
    expires_at: Optional[datetime] = Field(
        default=None,
        validation_alias=AliasChoices("expires_at", "expiresAt"),
        description="選填；對應 Poll.expiresAt",
    )
    options: List[PollOptionEmbedded] = Field(
        default_factory=list,
        description="選項列表；建立時寫入 PollOption",
    )


class Post(BaseModel):
    id: Optional[str] = Field(default=None, description="CMS 端的 Post ID")
    title: str
    content: Optional[str] = Field(default=None, description="原文內容，對應 Post.content")
    language: Optional[str] = Field(
        default=None,
        description="原始語言 zh/en/vi/id/th，對應 Post.language",
    )
    title_zh: Optional[str] = None
    title_en: Optional[str] = None
    title_vi: Optional[str] = None
    title_id: Optional[str] = None
    title_th: Optional[str] = None
    content_zh: Optional[str] = None
    content_en: Optional[str] = None
    content_vi: Optional[str] = None
    content_id: Optional[str] = None
    content_th: Optional[str] = None
    author_id: Optional[str] = Field(default=None, description="Member ID")
    topic_id: Optional[str] = Field(default=None, description="Topic ID，GraphQL topic connect")
    hero_image_id: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("hero_image_id", "heroImageId"),
        description="Photo ID，GraphQL heroImage connect",
    )
    ip: Optional[str] = Field(default=None, description="發文 IP")
    spam_score: Optional[float] = Field(
        default=None,
        validation_alias=AliasChoices("spam_score", "spamScore"),
        ge=0.0,
        le=1.0,
        description="SPAM 分數 0–1，對應 Post.spamScore",
    )
    status: Optional[str] = Field(
        default=None,
        description="draft | published | archived | hidden；預設 published",
    )
    is_active: Optional[bool] = Field(
        default=None,
        description="相容舊欄位：若未傳 status，True→published、False→draft",
    )
    poll: Optional[PollEmbedded] = Field(
        default=None,
        description="選填；建立 Post 時巢狀建立 Poll 與選項",
    )
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

