
import traceback

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.agents.research_planner import create_research_plan

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
































































































































































































































































































