import os
import json
import time
import random

from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types
from app.services.gemini_service import generate_with_fallback

from app.schemas.paper import Paper
from app.schemas.evidence import (
    EvidenceItem,
    ChunkEvidenceBatch,
    PaperEvidenceReport,
    EvidenceExtractionRequest,
    EvidenceExtractionResponse,
)

from app.services.pdf_service import PAPER_DIR, get_safe_filename
from app.services.document_chunking_service import create_document_chunks

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
You are the Scientific Research Evidence Extraction Agent.

Your job is to extract scientific information from a supplied
portion of a research paper.

Extract only information explicitly supported by the text.

Identify these categories:

1. objective: research problem, objective, or hypothesis.
2. methodology: experimental design, training procedure, or method.
3. architecture: models, architectures, or technical components.
4. dataset: dataset names, sample sizes, and data modalities.
5. metric: evaluation metrics used.
6. result: reported experimental findings and numerical results.
7. limitation: limitations explicitly discussed by the authors.
8. future_work: future research directions explicitly discussed.
9. other: useful scientific information that does not fit elsewhere.

Strict rules:

- Never invent a result, dataset, metric, or architecture.
- Do not assume a method was used unless the text states it.
- Do not turn a hypothesis into a proven result.
- Do not present an author's claim as independently verified fact.
- Preserve numerical values and units exactly where possible.
- Use only page numbers supplied with the text.
- Each supporting_excerpt must be a short, verbatim excerpt
  from the supplied text, ideally no more than 25 words.
- If the text does not support a useful finding, return
  an empty evidence list.
- Do not assess information outside the supplied chunk.
"""


def is_permanent_daily_quota_error(error: Exception) -> bool:
    """Daily free-tier quota exhaustion will not recover by retrying now."""
    error_text = str(error).upper()
    permanent_quota_markers = (
        "REQUESTS PER DAY",
        "TOKENS PER DAY",
        "PER DAY PER PROJECT",
        "GENERATEREQUESTSPERDAY",
        "DAILY QUOTA",
        "QUOTA RESET",
    )
    return any(marker in error_text for marker in permanent_quota_markers)


def is_retryable_error(error: Exception) -> bool:
    """Identify transient provider errors, excluding exhausted daily quotas."""
    if is_permanent_daily_quota_error(error):
        return False

    error_text = str(error).upper()
    retryable_codes = (
        "429",
        "500",
        "502",
        "503",
        "504",
        "RESOURCE_EXHAUSTED",
        "UNAVAILABLE",
        "INTERNAL",
    )
    return any(code in error_text for code in retryable_codes)


def generate_with_retry(
    prompt: str,
    paper_id: str = "unknown",
    chunk_number: int = 0,
    total_chunks: int = 0,
):
    """
    Retry transient provider failures with bounded exponential backoff.
    Do not repeat requests when the daily free-tier quota is exhausted.
    """
    max_attempts = 3

    for attempt in range(max_attempts):
        try:
            return generate_with_fallback(
                client=get_client(),
                primary_model=MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ChunkEvidenceBatch,
                    temperature=0.1,
                ),
            )

        except Exception as error:
            if (
                not is_retryable_error(error)
                or attempt == max_attempts - 1
            ):
                print(
                    f"[Evidence Extraction] FAILED | Paper: {paper_id} | "
                    f"Chunk: {chunk_number}/{total_chunks} | Error: {error}"
                )
                raise

            base_wait = min(30, 5 * (2 ** attempt))
            wait_seconds = base_wait + random.uniform(
                0, min(5, base_wait * 0.2)
            )

            print(
                f"[Evidence Extraction] Temporary provider error: {error} | "
                f"Paper: {paper_id} | Chunk: {chunk_number}/{total_chunks} | "
                f"Retry: {attempt + 1}/{max_attempts - 1} | "
                f"Waiting: {wait_seconds:.1f}s"
            )
            time.sleep(wait_seconds)

    raise RuntimeError("Evidence extraction failed after retries.")


def read_extracted_document(paper_id: str) -> str:
    filename = get_safe_filename(paper_id)
    text_path = PAPER_DIR / f"{filename}.txt"

    # Resolve and verify that the path stays inside PAPER_DIR.
    resolved_path = text_path.resolve()
    resolved_directory = PAPER_DIR.resolve()

    if not resolved_path.is_relative_to(resolved_directory):
        raise ValueError("Invalid document path.")

    if not resolved_path.exists():
        raise FileNotFoundError(
            f"Extracted text not found for paper: {paper_id}"
        )

    return resolved_path.read_text(encoding="utf-8")


def extract_chunk_evidence(
    paper: Paper,
    chunk: list[dict],
    chunk_number: int,
    total_chunks: int,
) -> list[EvidenceItem]:
    page_numbers = [
        item["page_number"]
        for item in chunk
    ]

    chunk_text = "\n\n".join(
        f"--- PAGE {item['page_number']} ---\n{item['text']}"
        for item in chunk
    )

    prompt = f"""
    {SYSTEM_INSTRUCTION}

    PAPER TITLE:
    {paper.title}

    PAPER ID:
    {paper.paper_id}

    AVAILABLE PAGE NUMBERS:
    {page_numbers}

    RESEARCH TEXT:
    {chunk_text}

    Extract the supported scientific evidence.
    Return only evidence from this text.
    """

    response = generate_with_retry(
        prompt=prompt,
        paper_id=paper.paper_id,
        chunk_number=chunk_number,
        total_chunks=total_chunks,
    )

    if not response.text:
        raise ValueError("The model returned an empty evidence response.")

    batch = ChunkEvidenceBatch.model_validate_json(response.text)

    # Reject references to pages outside this chunk.
    valid_evidence = []

    for item in batch.evidence:
        if item.page_number not in page_numbers:
            continue
        valid_evidence.append(item)

    return valid_evidence


def analyze_paper(paper: Paper) -> PaperEvidenceReport:
    warnings = []

    try:
        full_text = read_extracted_document(paper.paper_id)
    except Exception as error:
        return PaperEvidenceReport(
            paper_id=paper.paper_id,
            title=paper.title,
            extraction_status="failed",
            total_chunks=0,
            chunks_processed=0,
            warnings=[str(error)]
        )

    chunks = create_document_chunks(full_text)

    if not chunks:
        return PaperEvidenceReport(
            paper_id=paper.paper_id,
            title=paper.title,
            extraction_status="failed",
            total_chunks=0,
            chunks_processed=0,
            warnings=["The extracted document contains no readable text."]
        )

    all_evidence = []
    chunks_processed = 0

    for chunk_index, chunk in enumerate(chunks, start=1):
        try:
            if chunk_index > 1:
                time.sleep(3)

            evidence_items = extract_chunk_evidence(
                paper=paper,
                chunk=chunk,
                chunk_number=chunk_index,
                total_chunks=len(chunks),
            )

            all_evidence.extend(evidence_items)
            chunks_processed += 1

        except Exception as error:
            print(
                f"Evidence extraction failed for "
                f"{paper.paper_id}, chunk {chunk_index}: {error}"
            )
            warnings.append(
                f"Chunk {chunk_index} failed: {str(error)}"
            )

    # Remove duplicate findings while retaining page references.
    unique_evidence = []
    seen = set()

    for item in all_evidence:
        key = (
            item.category,
            item.page_number,
            item.finding.strip().lower()
        )

        if key not in seen:
            seen.add(key)
            unique_evidence.append(item)

    def get_findings(category: str) -> list[str]:
        return [
            item.finding
            for item in unique_evidence
            if item.category == category
        ]

    if chunks_processed == len(chunks):
        status = "success"
    elif chunks_processed > 0:
        status = "partial"
    else:
        status = "failed"

    return PaperEvidenceReport(
        paper_id=paper.paper_id,
        title=paper.title,
        extraction_status=status,
        total_chunks=len(chunks),
        chunks_processed=chunks_processed,
        research_objectives=get_findings("objective"),
        methodologies=get_findings("methodology"),
        architectures=get_findings("architecture"),
        datasets=get_findings("dataset"),
        metrics=get_findings("metric"),
        findings=[
            item for item in unique_evidence
            if item.category == "result"
        ],
        limitations=[
            item for item in unique_evidence
            if item.category == "limitation"
        ],
        future_work=[
            item for item in unique_evidence
            if item.category == "future_work"
        ],
        evidence=unique_evidence,
        warnings=warnings
    )


def extract_research_evidence(
    request: EvidenceExtractionRequest
) -> EvidenceExtractionResponse:
    reports = []

    for paper in request.papers:
        report = analyze_paper(paper)
        reports.append(report)

    successful = sum(
        1 for report in reports
        if report.extraction_status == "success"
    )
    partial = sum(
        1 for report in reports
        if report.extraction_status == "partial"
    )
    failed = sum(
        1 for report in reports
        if report.extraction_status == "failed"
    )

    return EvidenceExtractionResponse(
        status="success" if failed == 0 and partial == 0 else "completed_with_warnings",
        agent="Scientific Research Evidence Extraction Agent",
        total_papers_received=len(reports),
        successfully_analyzed=successful,
        partially_analyzed=partial,
        failed=failed,
        results=reports
    )
