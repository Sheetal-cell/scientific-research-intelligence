
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.evidence import PaperEvidenceReport
from app.schemas.report import ResearchReportResponse


class ReportQualityRequest(BaseModel):
    report: ResearchReportResponse
    evidence_reports: list[PaperEvidenceReport] = Field(min_length=2)


class CitationCheck(BaseModel):
    evidence_id: str
    paper_id: str
    page_number: int
    citation_exists: bool
    page_matches: bool
    excerpt_verified: bool
    status: Literal[
        "verified",
        "invalid_id",
        "page_mismatch",
        "excerpt_not_found",
        "document_missing",
    ]
    message: str


class SectionQualityDraft(BaseModel):
    section_title: str
    verdict: Literal[
        "supported",
        "partially_supported",
        "unsupported",
    ]
    score: int = Field(ge=0, le=100)
    issues: list[str] = Field(default_factory=list)
    comparability_concerns: list[str] = Field(default_factory=list)


class SectionQualityResult(SectionQualityDraft):
    verified_citations: int = 0
    invalid_citations: int = 0


class ReportQualityResponse(BaseModel):
    status: str
    agent: str
    overall_score: int = Field(ge=0, le=100)
    citation_integrity_score: int = Field(ge=0, le=100)
    total_citations_checked: int
    verified_citations: int
    invalid_citations: int
    sections_evaluated: int
    sections: list[SectionQualityResult] = Field(
        default_factory=list
    )
    citation_checks: list[CitationCheck] = Field(
        default_factory=list
    )
    warnings: list[str] = Field(default_factory=list)
