from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ConversationMessageResponse(BaseModel):
    id: str
    role: str
    content: str
    agent_type: Optional[str] = None
    meta_data: Optional[dict] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationResponse(BaseModel):
    id: str
    organization_id: str
    user_id: str
    title: Optional[str] = None
    agent_type: Optional[str] = None
    is_archived: bool
    message_count: int
    last_message_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationDetailResponse(ConversationResponse):
    messages: list[ConversationMessageResponse] = []


class ConversationListResponse(BaseModel):
    conversations: list[ConversationResponse]


class SendMessageRequest(BaseModel):
    content: str = Field(min_length=0, max_length=10000)
    conversation_id: Optional[str] = None
    agent_type: Optional[str] = None
    force_agent: Optional[str] = Field(default=None, description="Force a specific agent, bypassing the router")
    image_urls: Optional[list[str]] = Field(default=None, max_length=5, description="List of uploaded image URLs or base64 data URIs")


class SendMessageResponse(BaseModel):
    conversation_id: str
    message: ConversationMessageResponse
    response: ConversationMessageResponse
    credits_consumed: Optional[int] = None
    credits_remaining: Optional[int] = None


class UpdateConversationRequest(BaseModel):
    title: Optional[str] = Field(default=None, max_length=255)
    is_archived: Optional[bool] = None