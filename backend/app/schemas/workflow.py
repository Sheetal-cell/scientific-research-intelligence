from pydantic import BaseModel, Field
from app.schemas.research import ResearchPlan
from app.schemas.paper import PaperFilteringResponse
from app.schemas.document import PDFProcessingResponse
from app.schemas.evidence import EvidenceExtractionResponse
from app.schemas.synthesis import CrossPaperSynthesisResponse
from app.schemas.report import ResearchReportResponse
from app.schemas.quality import ReportQualityResponse


class ResearchWorkflowRequest(BaseModel):
    question: str = Field(min_length=15, max_length=500)


class WorkflowStage(BaseModel):
    name: str
    status: str
    message: str
    metrics: dict = Field(default_factory=dict)


class ResearchWorkflowResponse(BaseModel):
    status: str
    research_title: str
    stages: list[WorkflowStage]
    research_plan: ResearchPlan | None = None
    filtering: PaperFilteringResponse | None = None
    pdf_processing: PDFProcessingResponse | None = None
    evidence_extraction: EvidenceExtractionResponse | None = None
    synthesis: CrossPaperSynthesisResponse | None = None
    report: ResearchReportResponse | None = None
    quality_evaluation: ReportQualityResponse | None = None
    pdf_filename: str | None = None
