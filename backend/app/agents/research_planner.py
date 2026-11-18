
import os

from google import genai
from google.genai import types

from dotenv import load_dotenv

from app.schemas.research import ResearchPlan

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

if not API_KEY:
    raise RuntimeError("GEMINI_API_KEY is missing from .env")

client = genai.Client(api_key=API_KEY)

SYSTEM_INSTRUCTION = """
You are the Research Planner Agent of a Scientific Research
Intelligence platform.

Your responsibility is to convert a scientific research question
into a clear and structured research plan.

Rules:
1. Understand the user's research question.
2. Divide it into 3 to 4 meaningful research tasks.
3. Each task must have a distinct responsibility.
4. Provide useful scientific search keywords.
5. Keep the scope focused and realistic.
6. Do not invent research findings or citations.
7. Return only information that follows the required schema.
"""

def create_research_plan(question: str) -> ResearchPlan:

    prompt = f"""
    {SYSTEM_INSTRUCTION}

    Create a research plan for the following question:

    {question}
    """

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ResearchPlan,
            temperature=0.2,
        ),
    )

    if not response.text:
        raise ValueError("The model returned an empty response")

    return ResearchPlan.model_validate_json(response.text)
