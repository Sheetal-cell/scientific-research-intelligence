
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

    research_plan: ResearchPlan
    filtering: PaperFilteringResponse
    pdf_processing: PDFProcessingResponse
    evidence_extraction: EvidenceExtractionResponse
    synthesis: CrossPaperSynthesisResponse
    report: ResearchReportResponse
    quality_evaluation: ReportQualityResponse

    pdf_filename: str
