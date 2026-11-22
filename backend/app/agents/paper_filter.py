
import json
import os

from dotenv import load_dotenv
from google import genai
from google.genai import types
from app.services.gemini_service import generate_with_fallback
import time
import random
from app.schemas.paper import (
    Paper,
    PaperAssessment,
    PaperAssessmentBatch,
    FilteredPaper,
    TaskFilteringResult,
    PaperFilteringRequest,
    PaperFilteringResponse,
)

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

RELEVANCE_THRESHOLD = 65

SYSTEM_INSTRUCTION = """
You are the Paper Relevance and Quality Assessment Agent
of a Scientific Research Intelligence platform.

Your responsibility is to evaluate scientific papers against
their assigned research task.

For every paper:

1. Evaluate how directly the paper addresses the research task.
2. Assign a relevance score between 0 and 100.
3. Identify its main research category.
4. Explain why the paper is relevant or not relevant.
5. Identify useful contributions and limitations.
6. Identify missing information in its metadata.

Scoring guidelines:

90-100: Directly and strongly addresses the research task.
75-89: Highly relevant and provides useful evidence.
65-74: Moderately relevant and useful as supporting material.
40-64: Indirectly related or only partially useful.
0-39: Weakly related to the research task.

Important rules:

- Evaluate the title and abstract, not just matching keywords.
- Do not assume that a paper uses a Vision Transformer
  unless its title or abstract supports that conclusion.
- Distinguish classification, segmentation, registration,
  synthesis, detection, and other research categories.
- Do not invent experimental results, datasets, or methods.
- If information is missing, explicitly mention it.
- Preserve the exact paper_id provided in the input.
- Return one assessment for every input paper.
- The response must be a JSON object with exactly this top-level structure:
  {"assessments": [{"paper_id": "...", "relevance_score": 0,
  "category": "...", "rationale": "...", "strengths": [],
  "limitations": [], "metadata_warnings": []}]}
- Do not return the assessments array by itself; it must be inside
  the "assessments" object property.
"""

def is_retryable_error(error: Exception) -> bool:
    error_text = str(error).upper()

    retryable_codes = [
        "429",
        "500",
        "502",
        "503",
        "504",
        "RESOURCE_EXHAUSTED",
        "UNAVAILABLE",
        "INTERNAL",
    ]

    return any(
        code in error_text
        for code in retryable_codes
    )

def generate_assessment_with_retry(prompt: str):
    max_attempts = 5

    for attempt in range(max_attempts):
        try:
            return generate_with_fallback(
                client=get_client(),
                primary_model=MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=PaperAssessmentBatch,
                    temperature=0.1,
                ),
            )

        except Exception as error:
            if (
                not is_retryable_error(error)
                or attempt == max_attempts - 1
            ):
                raise

            base_wait = min(40, 5 * (2 ** attempt))
            wait_seconds = base_wait + random.uniform(0, min(5, base_wait * 0.2))

            print(
    f"[Paper Filtering] Gemini error: {error} | "
    f"Retry {attempt + 1}/{max_attempts - 1} | "
    f"Waiting {wait_seconds:.1f}s"
)

            time.sleep(wait_seconds)

    raise RuntimeError(
        "Paper assessment failed after retries."
    )
def _assess_paper_batch(task, papers: list[Paper]) -> list[PaperAssessment]:

    if not papers:
        return []

    paper_information = []

    for paper in papers:
        paper_information.append({
            "paper_id": paper.paper_id,
            "title": paper.title,
            "authors": paper.authors,
            "publication_year": paper.publication_year,
            "abstract": (paper.abstract or "Abstract unavailable")[:2500],
            "doi": paper.doi,
            "source": paper.source
        })

    prompt = f"""
    {SYSTEM_INSTRUCTION}

    RESEARCH TASK:
    {task.title}

    TASK DESCRIPTION:
    {task.description}

    PAPERS TO ASSESS:
    {json.dumps(paper_information, ensure_ascii=False, indent=2)}

    Assess every paper individually.
    Return exactly one assessment for each supplied paper_id.
    """

    response = generate_assessment_with_retry(prompt)

    if not response.text:
        raise ValueError("The filtering agent returned an empty response")

    # Some JSON-mode model responses return the assessments array directly,
    # even though the expected Pydantic schema is an object containing it.
    # Normalize that equivalent shape before validation.
    try:
        payload = json.loads(response.text)
    except json.JSONDecodeError as error:
        raise ValueError(
            "The paper filtering agent returned invalid JSON."
        ) from error

    if isinstance(payload, list):
        payload = {"assessments": payload}

    batch = PaperAssessmentBatch.model_validate(payload)

    return batch.assessments


def assess_task_papers(task, papers: list[Paper]) -> list[PaperAssessment]:
    """Assess small paper batches to keep prompts within free-tier limits."""
    batch_size = 3
    assessments = []

    for start in range(0, len(papers), batch_size):
        paper_batch = papers[start:start + batch_size]
        batch_number = (start // batch_size) + 1
        total_batches = (len(papers) + batch_size - 1) // batch_size
        print(
            f"[Paper Filtering] Assessing batch {batch_number}/"
            f"{total_batches} ({len(paper_batch)} papers)."
        )
        assessments.extend(_assess_paper_batch(task, paper_batch))

    return assessments


def filter_research_papers(
    request: PaperFilteringRequest
) -> PaperFilteringResponse:

    task_lookup = {
        task.task_id: task
        for task in request.tasks
    }

    filtered_results = []
    total_evaluated = 0
    total_relevant = 0

    for discovery_result in request.results:

        task = task_lookup.get(discovery_result.task_id)

        if task is None:
            continue

        papers = discovery_result.papers

        assessments = assess_task_papers(task, papers)

        assessment_lookup = {
            assessment.paper_id: assessment
            for assessment in assessments
        }

        filtered_papers = []

        for paper in papers:

            assessment = assessment_lookup.get(paper.paper_id)

            # Do not invent an assessment if the model
            # unexpectedly omits a paper.
            if assessment is None:
                assessment = PaperAssessment(
                    paper_id=paper.paper_id,
                    relevance_score=0,
                    category="Not assessed",
                    rationale="The AI agent did not return an assessment for this paper.",
                    strengths=[],
                    limitations=["Assessment was not returned."],
                    metadata_warnings=[]
                )

            is_relevant = (
                assessment.relevance_score >= RELEVANCE_THRESHOLD
            )

            filtered_papers.append(
                FilteredPaper(
                    paper=paper,
                    assessment=assessment,
                    relevant=is_relevant
                )
            )

            total_evaluated += 1

            if is_relevant:
                total_relevant += 1

        filtered_results.append(
            TaskFilteringResult(
                task_id=discovery_result.task_id,
                task_title=discovery_result.task_title,
                papers=filtered_papers,
                total_found=len(filtered_papers),
                relevant_count=sum(
                    1 for item in filtered_papers if item.relevant
                )
            )
        )

    return PaperFilteringResponse(
        status="success",
        agent="Paper Relevance and Quality Filtering Agent",
        relevance_threshold=RELEVANCE_THRESHOLD,
        total_papers_evaluated=total_evaluated,
        total_relevant_papers=total_relevant,
        results=filtered_results
    )