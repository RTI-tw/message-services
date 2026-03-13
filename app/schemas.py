from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


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

