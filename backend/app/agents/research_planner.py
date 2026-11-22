
import os

from google import genai
from google.genai import types

from dotenv import load_dotenv

from app.schemas.research import ResearchPlan

load_dotenv()

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

_client = None

def get_client():
    """Reuse one Gemini client instead of creating a new client per request."""
    global _client

    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not configured. Add it to backend/.env "
                "or your hosting provider's environment variables."
            )
        _client = genai.Client(api_key=api_key)

    return _client

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
import time

def generate_plan_with_retry(prompt: str):
    max_attempts = 4

    for attempt in range(max_attempts):
        try:
            return get_client().models.generate_content(
                model=MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ResearchPlan,
                    temperature=0.2,
                ),
            )

        except Exception as error:
            error_text = str(error).upper()

            retryable = any(
                code in error_text
                for code in [
                    "429", "500", "502", "503", "504",
                    "RESOURCE_EXHAUSTED",
                    "UNAVAILABLE",
                    "INTERNAL",
                ]
            )

            if not retryable or attempt == max_attempts - 1:
                raise

            wait_seconds = 2 ** (attempt + 1)

            print(
                f"Research Planner temporarily unavailable. "
                f"Retrying in {wait_seconds} seconds..."
            )

            time.sleep(wait_seconds)

    raise RuntimeError("Research planning failed after retries.")
def create_research_plan(question: str) -> ResearchPlan:

    prompt = f"""
    {SYSTEM_INSTRUCTION}

    Create a research plan for the following question:

    {question}
    """

    response = generate_plan_with_retry(prompt)

    if not response.text:
        raise ValueError("The model returned an empty response")

    return ResearchPlan.model_validate_json(response.text)
