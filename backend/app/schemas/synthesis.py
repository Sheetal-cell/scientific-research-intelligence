
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.evidence import PaperEvidenceReport


SynthesisCategory = Literal[
    "common_methods",
    "recurring_datasets",
    "performance_comparisons",
    "agreements",
    "contradictions",
    "limitations",
    "research_gaps",
    "trends",
]


class SynthesisRequest(BaseModel):
    evidence_reports: list[PaperEvidenceReport] = Field(
        min_length=2,
        description="Evidence reports from at least two research papers."
    )


class SynthesisSource(BaseModel):
    evidence_id: str
    paper_id: str
    paper_title: str
    category: str
    page_number: int
    finding: str
    supporting_excerpt: str


class SynthesisInsightDraft(BaseModel):
    category: SynthesisCategory
    claim: str
    cited_evidence_ids: list[str] = Field(default_factory=list)
    comparability_note: str | None = None


class SynthesisDraft(BaseModel):
    insights: list[SynthesisInsightDraft] = Field(default_factory=list)


class SynthesisInsight(BaseModel):
    category: SynthesisCategory
    claim: str
    comparability_note: str | None = None
    sources: list[SynthesisSource] = Field(default_factory=list)


class CrossPaperSynthesisResponse(BaseModel):
    status: str
    agent: str
    total_papers_received: int
    total_papers_used: int
    total_evidence_items: int
    total_insights: int
    insights: list[SynthesisInsight] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
