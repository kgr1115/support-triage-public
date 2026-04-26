from enum import StrEnum

from pydantic import BaseModel, Field


class Priority(StrEnum):
    URGENT = "urgent"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class Category(StrEnum):
    LOGIN = "login_issue"
    BILLING = "billing_dispute"
    INTEGRATION = "integration_setup"
    FEATURE_REQUEST = "feature_request"
    BUG_REPORT = "bug_report"


class Sentiment(StrEnum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    FRUSTRATED = "frustrated"


class Ticket(BaseModel):
    """A labeled support ticket — the unit consumed by the classifier and eval harness."""

    id: str
    subject: str = Field(..., min_length=1, max_length=200)
    body: str = Field(..., min_length=1)
    priority: Priority
    category: Category
    sentiment: Sentiment
    relevant_kb_ids: list[str] = Field(default_factory=list)


class Classification(BaseModel):
    """The classifier's output: priority + category + sentiment for one ticket."""

    priority: Priority
    category: Category
    sentiment: Sentiment


class KBArticle(BaseModel):
    """A knowledge base article — the corpus the retrieval layer searches over."""

    id: str
    title: str = Field(..., min_length=1, max_length=200)
    body: str = Field(..., min_length=1)
    categories: list[Category] = Field(default_factory=list)


class Macro(BaseModel):
    """A pre-canned reply template the agent can apply with one click.

    Same shape as KBArticle by design — both are id/title/body/categories text
    items embedded into a vector index. Difference is intent: KB articles are
    reference docs ('what the product does'); macros are response templates
    ('what the agent says').
    """

    id: str
    title: str = Field(..., min_length=1, max_length=200)
    body: str = Field(..., min_length=1)
    categories: list[Category] = Field(default_factory=list)
