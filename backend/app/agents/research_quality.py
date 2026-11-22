
import os
import re
import time
import random
import unicodedata

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel
from app.schemas.quality import (
    ReportQualityRequest,
    ReportQualityResponse,
    CitationCheck,
    SectionQualityDraft,
    SectionQualityResult,
)

from app.schemas.report import ReportCitation
from app.services.pdf_service import PAPER_DIR, get_safe_filename

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

class SectionQualityBatch(BaseModel):
    sections: list[SectionQualityDraft]

SYSTEM_INSTRUCTION = """
You are the Scientific Research Quality Evaluation Agent.

Your responsibility is to evaluate the scientific quality of a
generated research report using only the supplied report sections,
verified evidence and cross-paper context.

For each report section:

1. Decide whether the cited evidence supports the section's claims.
2. Identify unsupported statements and overgeneralizations.
3. Check whether numerical results are represented accurately.
4. Identify invalid comparisons between different tasks,
   datasets, experimental settings or evaluation protocols.
5. Identify conclusions that go beyond the supplied evidence.
6. Distinguish a paper's own claims from independently established facts.

Verdict definitions:

- supported: the supplied evidence adequately supports the claims.
- partially_supported: some claims are supported, but others
  need qualification or additional evidence.
- unsupported: the central claims are not adequately supported.

Scoring:
- 90-100: strongly supported with no major issues.
- 70-89: mostly supported with minor issues.
- 40-69: partially supported or has significant issues.
- 0-39: largely unsupported.

Important:
- Do not invent scientific facts.
- Do not treat the presence of a citation as proof of support.
- A shared metric does not automatically make two experiments comparable.
- An architecture is not automatically a limitation.
- Do not claim that this evaluation proves scientific correctness.
- Return only structured JSON.
"""

def normalize_text(value: str) -> str:
    """
    Normalize text to tolerate PDF extraction differences
    such as ligatures, whitespace and line wrapping.
    """

    value = unicodedata.normalize("NFKC", value)

    # Join words split by a line-ending hyphen.
    value = re.sub(r"-\s*\n\s*", "", value)

    # Normalize all whitespace.
    value = re.sub(r"\s+", " ", value)

    return value.strip().casefold()

def load_document_pages(paper_id: str) -> dict[int, str]:
    """
    Read the extracted PDF text and return a mapping:
    page number -> extracted page text.
    """

    filename = get_safe_filename(paper_id)
    text_path = PAPER_DIR / f"{filename}.txt"

    resolved_path = text_path.resolve()
    resolved_directory = PAPER_DIR.resolve()

    if not resolved_path.is_relative_to(resolved_directory):
        raise ValueError("Invalid document path.")

    if not resolved_path.exists():
        raise FileNotFoundError(
            f"Extracted text missing for {paper_id}"
        )

    full_text = resolved_path.read_text(encoding="utf-8")

    pattern = r"--- PAGE (\d+) ---"
    matches = list(re.finditer(pattern, full_text))

    pages = {}

    for index, match in enumerate(matches):
        start = match.end()

        end = (
            matches[index + 1].start()
            if index + 1 < len(matches)
            else len(full_text)
        )

        page_number = int(match.group(1))
        pages[page_number] = full_text[start:end]

    return pages

def build_evidence_lookup(reports):
    """
    Reconstruct IDs exactly as Phase 7 does.
    """

    lookup = {}

    unique_reports = {}

    for report in reports:
        unique_reports[report.paper_id] = report

    for report in unique_reports.values():

        for index, item in enumerate(report.evidence, start=1):

            evidence_id = (
                f"{report.paper_id}::"
                f"page-{item.page_number}::"
                f"item-{index}"
            )

            lookup[evidence_id] = {
                "paper_id": report.paper_id,
                "title": report.title,
                "category": item.category,
                "page_number": item.page_number,
                "finding": item.finding,
                "supporting_excerpt": item.supporting_excerpt,
            }

    return lookup

def verify_citation(
    citation: ReportCitation,
    evidence_lookup: dict,
    page_cache: dict,
) -> CitationCheck:

    evidence_id = citation.evidence_id

    if evidence_id not in evidence_lookup:
        return CitationCheck(
            evidence_id=evidence_id,
            paper_id=citation.paper_id,
            page_number=citation.page_number,
            citation_exists=False,
            page_matches=False,
            excerpt_verified=False,
            status="invalid_id",
            message="Citation ID does not exist in the supplied evidence."
        )

    source = evidence_lookup[evidence_id]

    if source["paper_id"] != citation.paper_id:
        return CitationCheck(
            evidence_id=evidence_id,
            paper_id=citation.paper_id,
            page_number=citation.page_number,
            citation_exists=True,
            page_matches=False,
            excerpt_verified=False,
            status="page_mismatch",
            message="Citation paper ID does not match its evidence source."
        )

    if (
        source["page_number"] != citation.page_number
        or source["finding"] != citation.finding
        or source["supporting_excerpt"] != citation.supporting_excerpt
        or source["category"] != citation.category
    ):
        return CitationCheck(
            evidence_id=evidence_id,
            paper_id=citation.paper_id,
            page_number=citation.page_number,
            citation_exists=True,
            page_matches=False,
            excerpt_verified=False,
            status="page_mismatch",
            message="Citation metadata does not match the original evidence."
        )

    paper_id = citation.paper_id

    if paper_id not in page_cache:
        try:
            page_cache[paper_id] = load_document_pages(paper_id)
        except Exception:
            page_cache[paper_id] = None

    pages = page_cache[paper_id]

    if pages is None:
        return CitationCheck(
            evidence_id=evidence_id,
            paper_id=paper_id,
            page_number=citation.page_number,
            citation_exists=True,
            page_matches=True,
            excerpt_verified=False,
            status="document_missing",
            message="Original extracted document is unavailable."
        )

    page_text = pages.get(citation.page_number)

    if page_text is None:
        return CitationCheck(
            evidence_id=evidence_id,
            paper_id=paper_id,
            page_number=citation.page_number,
            citation_exists=True,
            page_matches=False,
            excerpt_verified=False,
            status="page_mismatch",
            message="The cited page does not exist in the extracted document."
        )

    excerpt = normalize_text(citation.supporting_excerpt)
    source_text = normalize_text(page_text)

    verified = bool(excerpt) and excerpt in source_text

    return CitationCheck(
        evidence_id=evidence_id,
        paper_id=paper_id,
        page_number=citation.page_number,
        citation_exists=True,
        page_matches=True,
        excerpt_verified=verified,
        status="verified" if verified else "excerpt_not_found",
        message=(
            "Supporting excerpt found on the cited page."
            if verified
            else "Supporting excerpt could not be matched to the cited page."
        )
    )

def is_retryable_error(error: Exception) -> bool:
    error_text = str(error).upper()

    return any(
        code in error_text
        for code in [
            "429", "500", "502", "503", "504",
            "RESOURCE_EXHAUSTED", "UNAVAILABLE", "INTERNAL"
        ]
    )

def evaluate_with_gemini(prompt: str):
    for attempt in range(5):
        try:
            return get_client().models.generate_content(
                model=MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=SectionQualityBatch,
                    temperature=0.1,
                ),
            )

        except Exception as error:
            if not is_retryable_error(error) or attempt == 4:
                raise

            time.sleep(2 ** (attempt + 1))

    raise RuntimeError("Quality evaluation failed.")

def evaluate_research_report(
    request: ReportQualityRequest
) -> ReportQualityResponse:

    warnings = []

    evidence_lookup = build_evidence_lookup(
        request.evidence_reports
    )

    page_cache = {}

    citation_checks = []
    section_results = []

    verified_by_section = {}
    invalid_by_section = {}

    # Deterministic citation verification.
    for section in request.report.sections:

        verified_count = 0
        invalid_count = 0

        for citation in section.citations:

            check = verify_citation(
                citation,
                evidence_lookup,
                page_cache
            )

            citation_checks.append(check)

            if check.status == "verified":
                verified_count += 1
            else:
                invalid_count += 1

                warnings.append(
                    f"{section.title}: {citation.evidence_id} - "
                    f"{check.message}"
                )

        verified_by_section[section.title] = verified_count
        invalid_by_section[section.title] = invalid_count

    total_checked = len(citation_checks)

    verified_total = sum(
        1 for item in citation_checks
        if item.status == "verified"
    )

    invalid_total = total_checked - verified_total

    citation_integrity_score = (
        round((verified_total / total_checked) * 100)
        if total_checked else 0
    )

    # Only verified citations are supplied to the AI evaluator.
    evaluation_input = []

    for section in request.report.sections:

        verified_evidence = []

        for citation in section.citations:

            check = next(
                (
                    item for item in citation_checks
                    if item.evidence_id == citation.evidence_id
                    and item.status == "verified"
                ),
                None
            )

            if check:
                verified_evidence.append({
                    "evidence_id": citation.evidence_id,
                    "paper_id": citation.paper_id,
                    "paper_title": citation.paper_title,
                    "category": citation.category,
                    "page_number": citation.page_number,
                    "finding": citation.finding,
                    "supporting_excerpt": citation.supporting_excerpt,
                })

        evaluation_input.append({
            "section_title": section.title,
            "section_content": section.content,
            "verified_evidence": verified_evidence,
            "invalid_citation_count": invalid_by_section[section.title],
        })

    prompt = f"""
    {SYSTEM_INSTRUCTION}

    RESEARCH TITLE:
    {request.report.research_title}

    EXECUTIVE SUMMARY:
    {request.report.executive_summary}

    REPORT CONCLUSION:
    {request.report.overall_conclusion}

    REPORT SECTIONS AND VERIFIED EVIDENCE:
    {evaluation_input}

    Evaluate every section.

    Do not treat unverified citations as supporting evidence.
    Consider missing verified evidence when assigning the verdict.

    Return one result for every supplied report section.
    """

    response = evaluate_with_gemini(prompt)

    if not response.text:
        raise ValueError("Gemini returned an empty quality evaluation.")

    draft = SectionQualityBatch.model_validate_json(
        response.text
    )

    draft_lookup = {
        item.section_title: item
        for item in draft.sections
    }

    # Restore deterministic citation counts and ensure
    # every report section receives an evaluation result.
    for section in request.report.sections:

        ai_result = draft_lookup.get(section.title)

        verified_count = verified_by_section[section.title]
        invalid_count = invalid_by_section[section.title]

        if ai_result is None:
            result = SectionQualityResult(
                section_title=section.title,
                verdict="unsupported",
                score=0,
                issues=["AI evaluator did not return an assessment for this section."],
                comparability_concerns=[],
                verified_citations=verified_count,
                invalid_citations=invalid_count,
            )
        else:
            result = SectionQualityResult(
                **ai_result.model_dump(),
                verified_citations=verified_count,
                invalid_citations=invalid_count,
            )

        section_results.append(result)

    if section_results:
        ai_score = round(
            sum(item.score for item in section_results)
            / len(section_results)
        )
    else:
        ai_score = 0

    overall_score = round(
        (ai_score * 0.6)
        + (citation_integrity_score * 0.4)
    )

    if invalid_total:
        warnings.append(
            f"{invalid_total} citation(s) failed deterministic verification."
        )

    if not total_checked:
        warnings.append(
            "The report contains no citations to verify."
        )

    return ReportQualityResponse(
        status=(
            "success"
            if invalid_total == 0 and all(
                item.verdict == "supported"
                for item in section_results
            )
            else "completed_with_warnings"
        ),
        agent="Scientific Research Quality Evaluation Agent",
        overall_score=overall_score,
        citation_integrity_score=citation_integrity_score,
        total_citations_checked=total_checked,
        verified_citations=verified_total,
        invalid_citations=invalid_total,
        sections_evaluated=len(section_results),
        sections=section_results,
        citation_checks=citation_checks,
        warnings=warnings,
    )