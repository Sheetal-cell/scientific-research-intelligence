
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.research import ResearchPlan
from app.schemas.evidence import PaperEvidenceReport
from app.schemas.synthesis import CrossPaperSynthesisResponse


ReportSectionType = Literal[
    "literature_review",
    "methodology",
    "comparative_analysis",
    "research_gaps",
    "limitations",
    "future_directions",
    "conclusion",
]


class ResearchReportRequest(BaseModel):
    research_plan: ResearchPlan
    evidence_reports: list[PaperEvidenceReport] = Field(min_length=2)
    synthesis: CrossPaperSynthesisResponse


class ReportSectionDraft(BaseModel):
    section_type: ReportSectionType
    title: str
    content: str
    cited_evidence_ids: list[str] = Field(default_factory=list)


class ResearchReportDraft(BaseModel):
    executive_summary: str
    sections: list[ReportSectionDraft] = Field(default_factory=list)
    overall_conclusion: str


class ReportCitation(BaseModel):
    evidence_id: str
    paper_id: str
    paper_title: str
    category: str
    page_number: int
    finding: str
    supporting_excerpt: str


class ReportSection(BaseModel):
    section_type: ReportSectionType
    title: str
    content: str
    citations: list[ReportCitation] = Field(default_factory=list)


class ResearchReportResponse(BaseModel):
    status: str
    agent: str
    research_title: str
    executive_summary: str
    sections: list[ReportSection] = Field(default_factory=list)
    overall_conclusion: str
    total_papers_used: int
    total_evidence_items: int
    total_citations: int
    warnings: list[str] = Field(default_factory=list)
