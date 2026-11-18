
from pydantic import BaseModel, Field
from app.schemas.paper import Paper

class PDFProcessingRequest(BaseModel):
    papers: list[Paper] = Field(default_factory=list)

class PaperDocument(BaseModel):
    paper_id: str
    title: str
    download_status: str
    extraction_status: str
    page_count: int = 0
    extracted_chars: int = 0
    pdf_path: str | None = None
    text_path: str | None = None
    text_preview: str | None = None
    message: str | None = None

class PDFProcessingResponse(BaseModel):
    status: str
    agent: str
    total_papers_received: int
    successful_downloads: int
    successful_extractions: int
    results: list[PaperDocument]