
from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.report import ResearchReportResponse


class QualitySectionResult(BaseModel):
    section_title: str
    verdict: str
    score: float = 0
    issues: list[str] = Field(default_factory=list)
    comparability_concerns: list[str] = Field(default_factory=list)
    verified_citations: int = 0
    invalid_citations: int = 0


class QualityCitationCheck(BaseModel):
    evidence_id: str
    paper_id: str
    page_number: int
    citation_exists: bool = False
    page_matches: bool = False
    excerpt_verified: bool = False
    status: str
    message: str = ""


class QualityEvaluationResult(BaseModel):
    status: str
    agent: str
    overall_score: float
    citation_integrity_score: float
    total_citations_checked: int
    verified_citations: int
    invalid_citations: int
    sections_evaluated: int
    sections: list[QualitySectionResult] = Field(
        default_factory=list
    )
    citation_checks: list[QualityCitationCheck] = Field(
        default_factory=list
    )
    warnings: list[str] = Field(default_factory=list)


class ResearchPDFExportRequest(BaseModel):
    report: ResearchReportResponse
    quality_evaluation: QualityEvaluationResult


class ResearchPDFExportResponse(BaseModel):
    status: str
    message: str
    filename: str
    file_path: str
    report_title: str
    total_pages: Optional[int] = None
