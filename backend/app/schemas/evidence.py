
from typing import Literal

from pydantic import BaseModel, Field
from app.schemas.paper import Paper

EvidenceCategory = Literal[
    "objective",
    "methodology",
    "architecture",
    "dataset",
    "metric",
    "result",
    "limitation",
    "future_work",
    "other",
]


class EvidenceItem(BaseModel):
    category: EvidenceCategory
    finding: str
    supporting_excerpt: str = Field(
        description="A short, verbatim excerpt supporting the finding."
    )
    page_number: int = Field(ge=1)


class ChunkEvidenceBatch(BaseModel):
    evidence: list[EvidenceItem] = Field(default_factory=list)


class PaperEvidenceReport(BaseModel):
    paper_id: str
    title: str

    extraction_status: str
    total_chunks: int
    chunks_processed: int

    research_objectives: list[str] = Field(default_factory=list)
    methodologies: list[str] = Field(default_factory=list)
    architectures: list[str] = Field(default_factory=list)
    datasets: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)

    findings: list[EvidenceItem] = Field(default_factory=list)
    limitations: list[EvidenceItem] = Field(default_factory=list)
    future_work: list[EvidenceItem] = Field(default_factory=list)

    evidence: list[EvidenceItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class EvidenceExtractionRequest(BaseModel):
    papers: list[Paper] = Field(default_factory=list)


class EvidenceExtractionResponse(BaseModel):
    status: str
    agent: str
    total_papers_received: int
    successfully_analyzed: int
    partially_analyzed: int
    failed: int
    results: list[PaperEvidenceReport]
