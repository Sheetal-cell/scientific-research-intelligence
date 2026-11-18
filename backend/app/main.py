import traceback
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
import os

from app.agents.paper_discovery import discover_papers
from app.schemas.research import ResearchPlan
from app.agents.paper_filter import filter_research_papers
from app.schemas.paper import PaperFilteringRequest, PaperFilteringResponse
from app.agents.research_planner import create_research_plan
from app.agents.pdf_processing import process_research_papers
from app.schemas.document import PDFProcessingRequest, PDFProcessingResponse
from app.agents.evidence_extraction import extract_research_evidence
from app.schemas.evidence import EvidenceExtractionRequest, EvidenceExtractionResponse
from app.agents.cross_paper_synthesis import synthesize_research
from app.agents.research_workflow import run_research_workflow
from app.schemas.workflow import ResearchWorkflowRequest, ResearchWorkflowResponse
from app.services.pdf_report_service import REPORT_DIR, generate_research_pdf
from app.schemas.export import ResearchPDFExportRequest
from app.schemas.synthesis import SynthesisRequest, CrossPaperSynthesisResponse
from app.agents.report_generation import generate_research_report
from app.schemas.report import ResearchReportRequest, ResearchReportResponse
from app.agents.research_quality import evaluate_research_report
from app.schemas.quality import ReportQualityRequest, ReportQualityResponse

app = FastAPI(
    title="Scientific Research Intelligence",
    description="A multi-agent AI platform for evidence-based scientific research.",
    version="1.0.0",
)

origins = [
    origin.strip()
    for origin in os.getenv(
        "FRONTEND_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"https://.*\.vercel\.app$",
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


class ResearchRequest(BaseModel):
    question: str = Field(min_length=15, max_length=500)


@app.get("/")
def home():
    return {
        "message": "Scientific Research Intelligence API",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    return {"status": "healthy", "service": "scientific-research-intelligence"}


@app.post("/research/plan")
def generate_plan(request: ResearchRequest):
    try:
        plan = create_research_plan(request.question)
        return {"status": "success", "agent": "Research Planner", "plan": plan.model_dump()}
    except Exception as error:
        traceback.print_exc()
        raise HTTPException(status_code=502, detail=str(error))


@app.post("/research/discover")
def discover_research_papers(plan: ResearchPlan):
    try:
        results = discover_papers(plan.tasks)
        total_papers = sum(result.total_found for result in results)
        return {
            "status": "success",
            "agent": "Paper Discovery Agent",
            "total_papers_found": total_papers,
            "results": [result.model_dump() for result in results],
        }
    except Exception:
        traceback.print_exc()
        raise HTTPException(status_code=502, detail="Paper discovery failed. Check backend logs.")


@app.post("/research/filter", response_model=PaperFilteringResponse)
def filter_discovered_papers(request: PaperFilteringRequest):
    try:
        return filter_research_papers(request)
    except Exception:
        traceback.print_exc()
        raise HTTPException(status_code=502, detail="Paper relevance assessment failed. Check backend logs.")


@app.post("/research/process-pdfs", response_model=PDFProcessingResponse)
def process_research_pdfs(request: PDFProcessingRequest):
    try:
        return process_research_papers(request.papers)
    except Exception:
        traceback.print_exc()
        raise HTTPException(status_code=502, detail="Research PDF processing failed. Check backend logs.")


@app.post("/research/extract-evidence", response_model=EvidenceExtractionResponse)
def extract_evidence(request: EvidenceExtractionRequest):
    try:
        return extract_research_evidence(request)
    except Exception:
        traceback.print_exc()
        raise HTTPException(status_code=502, detail="Scientific evidence extraction failed. Check backend logs.")


@app.post("/research/synthesize", response_model=CrossPaperSynthesisResponse)
def synthesize_research_papers(request: SynthesisRequest):
    try:
        return synthesize_research(request)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except Exception:
        traceback.print_exc()
        raise HTTPException(status_code=502, detail="Cross-paper synthesis failed. Check backend logs.")


@app.post("/research/generate-report", response_model=ResearchReportResponse)
def generate_final_research_report(request: ResearchReportRequest):
    try:
        return generate_research_report(request)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except Exception:
        traceback.print_exc()
        raise HTTPException(status_code=502, detail="Research report generation failed. Check backend logs.")


@app.post("/research/evaluate-report", response_model=ReportQualityResponse)
def evaluate_final_research_report(request: ReportQualityRequest):
    try:
        return evaluate_research_report(request)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except Exception:
        traceback.print_exc()
        raise HTTPException(status_code=502, detail="Research quality evaluation failed. Check backend logs.")


@app.post("/research/export-pdf")
def export_research_pdf(request: ResearchPDFExportRequest):
    try:
        result = generate_research_pdf(request)
        return FileResponse(
            path=result["file_path"],
            media_type="application/pdf",
            filename=result["filename"],
        )
    except Exception:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Research PDF generation failed. Check backend logs.")


@app.post("/research/run", response_model=ResearchWorkflowResponse)
def run_complete_research(request: ResearchWorkflowRequest):
    try:
        return run_research_workflow(request.question)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    except Exception:
        traceback.print_exc()
        raise HTTPException(status_code=502, detail="Research workflow failed. Check backend logs.")


@app.get("/research/download/{filename}")
def download_research_report(filename: str):
    safe_filename = Path(filename).name
    if safe_filename != filename or not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Invalid filename.")
    file_path = REPORT_DIR / safe_filename
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Research report PDF not found.")
    return FileResponse(path=str(file_path), media_type="application/pdf", filename=safe_filename)
