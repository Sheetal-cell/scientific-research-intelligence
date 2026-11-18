from pydantic import BaseModel
from typing import Optional


class Paper(BaseModel):
    paper_id: str
    title: str
    authors: list[str] = []
    publication_year: Optional[int] = None
    abstract: Optional[str] = None
    doi: Optional[str] = None
    source: str
    paper_url: Optional[str] = None


class PaperSearchResult(BaseModel):
    task_id: int
    task_title: str
    papers: list[Paper]
    total_found: int