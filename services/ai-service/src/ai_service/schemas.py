from datetime import date, datetime, time
from decimal import Decimal
from typing import Literal
from uuid import UUID
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

class ToolContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    film_id: int | None = Field(default=None, gt=0)
    theater_id: int | None = Field(default=None, gt=0)
    show_date: date | None = None
    showtime_id: int | None = Field(default=None, gt=0)
    film_name: str = Field(default="", max_length=200)
    theater_name: str = Field(default="", max_length=200)
    genre: str = Field(default="", max_length=100)
    language: str = Field(default="", max_length=100)
    city: str = Field(default="", max_length=100)
    format: str = Field(default="", max_length=50)
    duration_max: int | None = Field(default=None, ge=1, le=600)
    start_after: time | None = None
    start_before: time | None = None
    party_size: int = Field(default=1, ge=1, le=20)
    budget_amount: Decimal | None = Field(default=None, gt=0, le=100000000)
    budget_scope: Literal["unknown", "total", "per_ticket"] = "unknown"
    knowledge_scope: Literal["policy", "film_education", "reference"] = "policy"


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=2000)
    conversation_id: UUID | None = None
    context: ToolContext = Field(default_factory=ToolContext)

    @field_validator("message")
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError("Câu hỏi không được để trống")
        return value.strip()


class ConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime


class MessageRead(BaseModel):
    id: int
    role: Literal["user", "assistant"]
    content: str
    metadata: dict
    created_at: datetime


class ConversationDetail(ConversationRead):
    context: ToolContext
    messages: list[MessageRead]
    next_before_id: int | None = None


class ToolCall(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Literal["search_films", "get_showtimes", "get_ticket_prices", "get_seat_availability", "get_positive_films"]
    context: ToolContext = Field(default_factory=ToolContext)
    query: str = Field(default="", max_length=200)


class PlannerContext(ToolContext):
    # VND is integral here. A plain JSON integer also gives small local models a
    # stricter generation grammar than Pydantic Decimal's number-or-string union.
    budget_amount: int | None = Field(default=None, gt=0, le=100000000)


class AssistantPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    intent: Literal["knowledge", "recommend", "search_films", "get_showtimes", "get_ticket_prices", "get_seat_availability", "get_positive_films", "out_of_scope"]
    context: PlannerContext = Field(default_factory=PlannerContext)


class GroundedSentence(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    source_id: str = Field(min_length=1, max_length=100)
    text: str = Field(min_length=1, max_length=900)


class GroundedAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["answer", "insufficient", "clarify"]
    sentences: list[GroundedSentence] = Field(max_length=2)
    clarification: str = Field(max_length=240)

    @model_validator(mode="before")
    @classmethod
    def discard_inactive_fields(cls, value):
        if isinstance(value, dict):
            decision = value.get("decision")
            if decision == "insufficient":
                return value | {"sentences": [], "clarification": ""}
            if decision == "clarify":
                return value | {"sentences": []}
            if decision == "answer":
                return value | {"clarification": ""}
        return value

    @model_validator(mode="after")
    def response_shape(self):
        if self.decision == "answer" and not self.sentences:
            raise ValueError("An answer must contain supported sentences")
        return self


class AdminInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class KnowledgeProvenance(AdminInput):
    source_type: Literal["internal", "web", "pdf", "text"] = "internal"
    scope: Literal["policy", "film_education", "reference"] = "policy"
    author: str = Field(default="", max_length=300)
    license: str = Field(default="", max_length=300)
    language: str = Field(default="vi", max_length=20)
    checksum: str = Field(default="", pattern=r"^(?:[a-f0-9]{64})?$")
    extraction: str = Field(default="manual-text-v1", max_length=100)


class KnowledgeBlock(AdminInput):
    text: str = Field(min_length=1, max_length=100000)
    page_start: int | None = Field(default=None, gt=0)
    page_end: int | None = Field(default=None, gt=0)
    section: str = Field(default="", max_length=300)

    @model_validator(mode="after")
    def pages(self):
        if self.page_end is not None and (self.page_start is None or self.page_end < self.page_start):
            raise ValueError("Invalid PDF page range")
        return self


class DocumentWrite(AdminInput):
    source_id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=200)
    version: str = Field(min_length=1, max_length=50)
    source_url: str = Field(min_length=1, max_length=500)
    effective_at: datetime
    content: str = Field(default="", max_length=2000000)
    provenance: KnowledgeProvenance = Field(default_factory=KnowledgeProvenance)
    blocks: list[KnowledgeBlock] = Field(default_factory=list, max_length=2000)
    # Required on replacement; returned by the review screen. Never approve stale content.
    expected_updated_at: datetime | None = None

    @model_validator(mode="after")
    def has_content(self):
        if bool(self.content.strip()) == bool(self.blocks):
            raise ValueError("Provide either content or page blocks, not both")
        if sum(len(block.text) for block in self.blocks) > 2000000:
            raise ValueError("Knowledge document too large")
        if self.provenance.source_type == "pdf" and (not self.provenance.license or
                not self.provenance.checksum or not self.blocks or any(block.page_start is None for block in self.blocks)):
            raise ValueError("PDF requires license, checksum and page provenance")
        return self


    @field_validator("source_url")
    @classmethod
    def source(cls, value):
        from .rag import safe_source_url
        return safe_source_url(value)

    @field_validator("effective_at", "expected_updated_at")
    @classmethod
    def aware_date(cls, value):
        if value is not None and value.tzinfo is None:
            raise ValueError("Thời điểm phải có múi giờ")
        return value


class DocumentRevisionWrite(AdminInput):
    document: DocumentWrite
    graph_release_id: str = Field(default="", pattern=r"^(?:[a-f0-9]{64})?$")


class DocumentRevisionPublish(AdminInput):
    expected_updated_at: AwareDatetime


class DocumentApproval(AdminInput):
    version: str = Field(min_length=1, max_length=50)
    expected_updated_at: datetime
    approved: bool = True
