
import os
import time

from dotenv import load_dotenv
from google import genai
from google.genai import types

from app.schemas.report import (
    ResearchReportRequest,
    ResearchReportDraft,
    ReportCitation,
    ReportSection,
    ResearchReportResponse,
)


load_dotenv()

MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
 
 def get_client():
     """Create the Gemini client only when an AI operation is requested."""
     api_key = os.getenv("GEMINI_API_KEY")
     if not api_key:
         raise RuntimeError(
             "GEMINI_API_KEY is not configured. Add it to backend/.env "
             "or your hosting provider's environment variables."
         )
     return genai.Client(api_key=api_key)


SYSTEM_INSTRUCTION = """
You are the Scientific Research Report Generation Agent.

Your responsibility is to create a structured scientific research
report using the supplied research plan, extracted paper evidence,
and cross-paper synthesis.

REPORT STRUCTURE:
1. Literature Review
2. Methodology
3. Comparative Analysis
4. Research Gaps
5. Limitations
6. Future Directions
7. Conclusion

SCIENTIFIC RULES:

- Use only the supplied research information.
- Never invent research findings, numerical results, datasets,
  paper details, citations, or references.
- Do not introduce external papers or unsupported facts.
- Every factual section must cite relevant evidence IDs.
- Only use evidence IDs supplied in the input.
- Distinguish individual paper findings from cross-paper conclusions.
- Preserve the distinction between different research tasks.
- Do not compare numerical results from incompatible experiments.
- Respect comparability notes from the synthesis agent.
- Do not interpret missing information as proof of absence.
- Clearly mention limitations and uncertainty.
- Do not claim that AI-generated conclusions are independently
  scientifically verified.
- Avoid repeating the same information in multiple sections.
- Write in formal, clear academic language.
- Return only the requested structured JSON.
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

    return any(code in error_text for code in retryable_codes)


def generate_with_retry(prompt: str):
    max_attempts = 3

    for attempt in range(max_attempts):
        try:
            return get_client().models.generate_content(
                model=MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ResearchReportDraft,
                    temperature=0.2,
                ),
            )

        except Exception as error:
            if (
                not is_retryable_error(error)
                or attempt == max_attempts - 1
            ):
                raise

            wait_seconds = 2 ** (attempt + 1)

            print(
                f"Report generation temporarily unavailable. "
                f"Retrying in {wait_seconds} seconds."
            )

            time.sleep(wait_seconds)

    raise RuntimeError("Report generation failed.")


def prepare_evidence(reports):
    evidence_lookup = {}
    evidence_payload = []

    for report in reports:
        for index, item in enumerate(report.evidence, start=1):

            evidence_id = (
                f"{report.paper_id}::"
                f"page-{item.page_number}::"
                f"item-{index}"
            )

            citation = ReportCitation(
                evidence_id=evidence_id,
                paper_id=report.paper_id,
                paper_title=report.title,
                category=item.category,
                page_number=item.page_number,
                finding=item.finding,
                supporting_excerpt=item.supporting_excerpt,
            )

            evidence_lookup[evidence_id] = citation

            evidence_payload.append({
                "evidence_id": evidence_id,
                "paper_id": report.paper_id,
                "paper_title": report.title,
                "category": item.category,
                "page_number": item.page_number,
                "finding": item.finding,
                "supporting_excerpt": item.supporting_excerpt,
            })

    return evidence_payload, evidence_lookup


def generate_research_report(
    request: ResearchReportRequest
):

    warnings = []

    # Remove duplicate papers.
    unique_reports = {}

    for report in request.evidence_reports:
        unique_reports[report.paper_id] = report

    reports = list(unique_reports.values())

    if len(reports) < 2:
        raise ValueError(
            "At least two distinct papers are required."
        )

    # Use only papers with usable evidence.
    usable_reports = [
        report
        for report in reports
        if report.extraction_status in ("success", "partial")
        and report.evidence
    ]

    if len(usable_reports) < 2:
        raise ValueError(
            "At least two papers with extracted evidence are required."
        )

    for report in reports:

        if report.extraction_status == "partial":
            warnings.append(
                f"{report.title}: evidence extraction was partial."
            )

        elif report.extraction_status == "failed":
            warnings.append(
                f"{report.title}: excluded because extraction failed."
            )

        elif not report.evidence:
            warnings.append(
                f"{report.title}: excluded because no evidence was extracted."
            )

    evidence_payload, evidence_lookup = prepare_evidence(
        usable_reports
    )

    if not evidence_payload:
        raise ValueError("No scientific evidence is available.")

    # Prepare synthesis input.
    synthesis_payload = []

    for insight in request.synthesis.insights:

        synthesis_payload.append({
            "category": insight.category,
            "claim": insight.claim,
            "comparability_note": insight.comparability_note,
            "sources": [
                source.model_dump()
                for source in insight.sources
            ],
        })

    prompt = f"""
    {SYSTEM_INSTRUCTION}

    RESEARCH PLAN:
    {request.research_plan.model_dump_json(indent=2)}

    NUMBER OF PAPERS:
    {len(usable_reports)}

    PAPER EVIDENCE:
    {evidence_payload}

    CROSS-PAPER SYNTHESIS:
    {synthesis_payload}

    Create a complete scientific research report.

    Requirements:

    1. Write a concise executive summary.
    2. Include all seven requested report sections.
    3. Explain the research methodologies and architectures.
    4. Discuss datasets and evaluation metrics.
    5. Include comparisons only when scientifically appropriate.
    6. Explain research gaps supported by the supplied evidence.
    7. Include relevant limitations and future directions.
    8. Provide a conclusion answering the original research question.

    For every section, provide cited_evidence_ids.
    Use only IDs from the supplied PAPER EVIDENCE.
    If a section cannot be supported, explain that limitation
    instead of inventing information.

    Return the structured report.
    """

    response = generate_with_retry(prompt)

    if not response.text:
        raise ValueError(
            "Gemini returned an empty research report."
        )

    draft = ResearchReportDraft.model_validate_json(
        response.text
    )

    validated_sections = []
    total_citations = 0

    for section in draft.sections:

        citations = []
        seen_ids = set()

        for evidence_id in section.cited_evidence_ids:

            if (
                evidence_id in evidence_lookup
                and evidence_id not in seen_ids
            ):
                citations.append(
                    evidence_lookup[evidence_id]
                )

                seen_ids.add(evidence_id)

            elif evidence_id not in evidence_lookup:
                warnings.append(
                    f"Unknown citation ID discarded: {evidence_id}"
                )

        total_citations += len(citations)

        if not citations:
            warnings.append(
                f"Section '{section.title}' has no validated citations."
            )

        validated_sections.append(
            ReportSection(
                section_type=section.section_type,
                title=section.title,
                content=section.content,
                citations=citations,
            )
        )

    if request.synthesis.status != "success":
        warnings.append(
            "The supplied cross-paper synthesis contains warnings "
            "or has no validated insights."
        )

    for warning in request.synthesis.warnings:
        warnings.append(
            f"Synthesis warning: {warning}"
        )

    return ResearchReportResponse(
        status=(
            "success"
            if total_citations > 0
            else "completed_with_warnings"
        ),
        agent="Scientific Research Report Generation Agent",
        research_title=request.research_plan.research_title,
        executive_summary=draft.executive_summary,
        sections=validated_sections,
        overall_conclusion=draft.overall_conclusion,
        total_papers_used=len(usable_reports),
        total_evidence_items=len(evidence_payload),
        total_citations=total_citations,
        warnings=warnings,
    )
