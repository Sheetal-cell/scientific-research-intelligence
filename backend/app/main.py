
import traceback
from app.agents.paper_discovery import discover_papers
from app.schemas.research import ResearchPlan
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.agents.paper_filter import filter_research_papers
from app.schemas.paper import (
    PaperFilteringRequest,
    PaperFilteringResponse,
)
from app.agents.research_planner import create_research_plan
from app.agents.pdf_processing import process_research_papers
from app.schemas.document import (
    PDFProcessingRequest,
    PDFProcessingResponse,
)
from app.agents.evidence_extraction import extract_research_evidence
from app.schemas.evidence import (
    EvidenceExtractionRequest,
    EvidenceExtractionResponse,
)

app = FastAPI(
    title="Scientific Research Intelligence",
    description="A multi-agent AI research platform",
    version="0.2.0"
)

class ResearchRequest(BaseModel):
    question: str = Field(
        min_length=15,
        max_length=500
    )

@app.get("/")
def home():
    return {
        "message": "Scientific Research Intelligence API",
        "status": "running"
    }

@app.get("/health")
def health():
    return {"status": "healthy"}

@app.post("/research/plan")
def generate_plan(request: ResearchRequest):

    try:
        plan = create_research_plan(request.question)

        return {
            "status": "success",
            "agent": "Research Planner",
            "plan": plan.model_dump()
        }
    except Exception as error:
        print("\n========== RESEARCH PLANNER ERROR ==========")
        traceback.print_exc()
        print("============================================\n")

        raise HTTPException(
            status_code=502,
            detail=str(error)
        )



@app.post("/research/discover")
def discover_research_papers(plan: ResearchPlan):

    try:
        results = discover_papers(plan.tasks)

        total_papers = sum(
            result.total_found for result in results
        )

        return {
            "status": "success",
            "agent": "Paper Discovery Agent",
            "total_papers_found": total_papers,
            "results": [
                result.model_dump()
                for result in results
            ]
        }

    except Exception as error:
        print(f"Paper Discovery Error: {error}")

        raise HTTPException(
            status_code=502,
            detail="Paper discovery failed. Check the backend logs."
        )




@app.post("/research/filter", response_model=PaperFilteringResponse)
def filter_discovered_papers(request: PaperFilteringRequest):
    try:
        result = filter_research_papers(request)
        return result

    except Exception as error:
        print(f"Paper Filtering Error: {error}")

        raise HTTPException(
            status_code=502,
            detail="Paper relevance assessment failed. Check backend logs."
        )

@app.post(
    "/research/process-pdfs",
    response_model=PDFProcessingResponse
)
def process_research_pdfs(request: PDFProcessingRequest):

    try:
        return process_research_papers(request.papers)

    except Exception as error:

        print(f"PDF Processing Error: {error}")

        raise HTTPException(
            status_code=502,
            detail="Research PDF processing failed. Check backend logs."
        )



@app.post(
    "/research/extract-evidence",
    response_model=EvidenceExtractionResponse
)
def extract_evidence(request: EvidenceExtractionRequest):

    try:
        return extract_research_evidence(request)

    except Exception as error:

        print(f"Evidence Extraction Error: {error}")

        raise HTTPException(
            status_code=502,
            detail="Scientific evidence extraction failed. Check backend logs."
        )