

from pydantic import BaseModel, Field

class ResearchTask(BaseModel):
    task_id: int
    title: str
    description: str
    expected_output: str
    search_keywords: list[str]

class ResearchPlan(BaseModel):
    research_title: str
    research_question: str
    research_scope: str
    tasks: list[ResearchTask]
    suggested_keywords: list[str]