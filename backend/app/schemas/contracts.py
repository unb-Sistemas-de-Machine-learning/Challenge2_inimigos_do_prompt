"""Contratos de dados (Pydantic) alinhados ao SPEC.md e ao frontend."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class PostureFeatures(BaseModel):
    head_forward_offset: float
    trunk_inclination: float
    shoulder_asymmetry: float
    apparent_face_scale: float


class PostureClassification(BaseModel):
    label: str
    confidence: float = Field(ge=0.0, le=1.0)


class PostureEvent(BaseModel):
    event_id: UUID
    timestamp: datetime
    camera_mode: Literal["frontal", "lateral"] = "frontal"
    landmarks_confidence: float = Field(ge=0.0, le=1.0)
    duration_minutes: float = Field(default=0.0, ge=0.0)
    features: PostureFeatures
    classification: PostureClassification


class EvidenceItem(BaseModel):
    document_id: str
    source: str
    section: str | None = None
    page: int | None = None
    exact_quote: str


class GroundedRecommendation(BaseModel):
    recommendation_id: UUID
    recommendation: str
    category: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[EvidenceItem] = Field(default_factory=list)


class SafetyDecision(BaseModel):
    approved: bool
    scope: str
    evidence_verified: bool
    requires_professional: bool
    reason: str


class SetupObservation(BaseModel):
    category: str
    status: Literal["adequado", "inadequado"] = "adequado"
    description: str
    confidence: float = Field(ge=0.0, le=1.0)
    requires_confirmation: bool = True


class SetupAnalysis(BaseModel):
    analysis_id: UUID
    observations: list[SetupObservation] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class FeedbackRequest(BaseModel):
    event_id: UUID
    feedback_type: Literal["helpful", "false_alert"]
