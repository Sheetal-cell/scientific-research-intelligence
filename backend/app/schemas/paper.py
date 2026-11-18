
from pydantic import BaseModel, Field
from typing import Optional

from app.schemas.research import ResearchTask
class Paper(BaseModel):
    paper_id: str
    title: str
    authors: list[str] = Field(default_factory=list)
    publication_year: Optional[int] = None
    abstract: Optional[str] = None
    doi: Optional[str] = None
    source: str
    paper_url: Optional[str] = None


class PaperSearchResult(BaseModel):
    task_id: int
    task_title: str
    papers: list[Paper] = Field(default_factory=list)
    total_found: int


class PaperAssessment(BaseModel):
    paper_id: str
    relevance_score: int = Field(ge=0, le=100)
    category: str
    rationale: str
    strengths: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    metadata_warnings: list[str] = Field(default_factory=list)


class PaperAssessmentBatch(BaseModel):
    assessments: list[PaperAssessment]


class FilteredPaper(BaseModel):
    paper: Paper
    assessment: PaperAssessment
    relevant: bool


class TaskFilteringResult(BaseModel):
    task_id: int
    task_title: str
    papers: list[FilteredPaper]
    total_found: int
    relevant_count: int


class PaperFilteringRequest(BaseModel):
    tasks: list[ResearchTask]
    results: list[PaperSearchResult]


class PaperFilteringResponse(BaseModel):
    status: str
    agent: str
    relevance_threshold: int
    total_papers_evaluated: int
    total_relevant_papers: int
    results: list[TaskFilteringResult]
