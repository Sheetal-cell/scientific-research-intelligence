
import os
import time

from dotenv import load_dotenv
from google import genai
from google.genai import types

from app.schemas.synthesis import (
    SynthesisRequest,
    SynthesisSource,
    SynthesisInsight,
    SynthesisDraft,
    CrossPaperSynthesisResponse,
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
You are the Cross-Paper Synthesis Agent of a Scientific Research
Intelligence platform.

Your task is to synthesize scientific evidence extracted from
multiple research papers.

Analyze the supplied evidence and identify:

1. Common methods and architectures.
2. Datasets recurring across different papers.
3. Quantitative performance comparisons.
4. Agreements between studies.
5. Contradictions or disagreements.
6. Repeated limitations.
7. Research gaps and future directions.
8. Broader research trends.

STRICT SCIENTIFIC RULES:

- Use only the supplied evidence.
- Never invent findings, citations, datasets, metrics, or values.
- Every insight must cite evidence IDs from at least TWO distinct papers.
- Never cite an evidence ID that was not supplied.
- Do not claim that two studies are directly comparable merely
  because they report the same metric.
- Before comparing numerical results, consider the task,
  dataset, data split, evaluation protocol, and model variant.
- If comparability cannot be established, explicitly explain
  the limitation in comparability_note.
- Do not rank models using results from incompatible experiments.
- Distinguish author-reported findings from independently
  established facts.
- Do not interpret missing information as evidence of absence.
- A research gap must be supported by the supplied papers.
- Keep claims precise, balanced, and scientifically cautious.
- Avoid repeating the same insight in multiple categories.
- Return only the requested structured output.
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
                    response_schema=SynthesisDraft,
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
                f"Synthesis model temporarily unavailable. "
                f"Retry {attempt + 1}/{max_attempts - 1} "
                f"in {wait_seconds} seconds."
            )

            time.sleep(wait_seconds)

    raise RuntimeError("Synthesis generation failed after retries.")


def prepare_evidence(reports):
    """
    Create stable evidence IDs and a lookup table.

    Only the general evidence list is used, avoiding duplicate
    entries from the category-specific summary lists.
    """

    evidence_lookup = {}
    evidence_payload = []

    for report in reports:
        for index, item in enumerate(report.evidence, start=1):

            evidence_id = (
                f"{report.paper_id}::"
                f"page-{item.page_number}::"
                f"item-{index}"
            )

            source = SynthesisSource(
                evidence_id=evidence_id,
                paper_id=report.paper_id,
                paper_title=report.title,
                category=item.category,
                page_number=item.page_number,
                finding=item.finding,
                supporting_excerpt=item.supporting_excerpt,
            )

            evidence_lookup[evidence_id] = source

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


def synthesize_research(
    request: SynthesisRequest,
) -> CrossPaperSynthesisResponse:

    warnings = []

    # Remove duplicate paper reports by paper_id.
    unique_reports = {}

    for report in request.evidence_reports:
        unique_reports[report.paper_id] = report

    reports = list(unique_reports.values())

    if len(reports) < 2:
        raise ValueError(
            "Cross-paper synthesis requires at least two distinct papers."
        )

    usable_reports = [
        report
        for report in reports
        if report.extraction_status in ("success", "partial")
        and report.evidence
    ]

    for report in reports:
        if report.extraction_status == "partial":
            warnings.append(
                f"{report.title}: evidence extraction was partial. "
                "Synthesis may not represent the entire paper."
            )

        elif report.extraction_status == "failed":
            warnings.append(
                f"{report.title}: excluded because evidence extraction failed."
            )

        elif not report.evidence:
            warnings.append(
                f"{report.title}: excluded because no evidence was extracted."
            )

    if len(usable_reports) < 2:
        raise ValueError(
            "At least two papers with usable extracted evidence are "
            "required for cross-paper synthesis."
        )

    evidence_payload, evidence_lookup = prepare_evidence(
        usable_reports
    )

    if not evidence_payload:
        raise ValueError("No evidence is available for synthesis.")

    prompt = f"""
    {SYSTEM_INSTRUCTION}

    NUMBER OF PAPERS:
    {len(usable_reports)}

    EXTRACTED SCIENTIFIC EVIDENCE:
    {evidence_payload}

    Analyze the evidence across the different papers.

    For every insight:
    - Select only relevant evidence IDs.
    - Cite evidence from at least two distinct papers.
    - Explain the scientific relationship accurately.
    - Add a comparability note when experiments or metrics
      cannot be directly compared.
    - Do not create an insight if the evidence is insufficient.

    Return the structured synthesis.
    """

    response = generate_with_retry(prompt)

    if not response.text:
        raise ValueError("Gemini returned an empty synthesis response.")

    draft = SynthesisDraft.model_validate_json(response.text)

    validated_insights = []

    for insight in draft.insights:

        # Resolve only IDs that actually exist in our evidence.
        sources = []
        seen_ids = set()

        for evidence_id in insight.cited_evidence_ids:

            if evidence_id in evidence_lookup and evidence_id not in seen_ids:
                sources.append(evidence_lookup[evidence_id])
                seen_ids.add(evidence_id)

            elif evidence_id not in evidence_lookup:
                warnings.append(
                    "The model returned an unknown evidence ID. "
                    "That reference was discarded."
                )

        distinct_papers = {
            source.paper_id
            for source in sources
        }

        # A cross-paper insight must be supported by at least
        # two distinct papers.
        if len(distinct_papers) < 2:
            warnings.append(
                f"An insight in category '{insight.category}' "
                "was discarded because it did not cite at least "
                "two distinct papers."
            )
            continue

        validated_insights.append(
            SynthesisInsight(
                category=insight.category,
                claim=insight.claim,
                comparability_note=insight.comparability_note,
                sources=sources,
            )
        )

    if not validated_insights:
        warnings.append(
            "No cross-paper insights passed source validation. "
            "Try supplying more papers with relevant extracted evidence."
        )

    return CrossPaperSynthesisResponse(
        status=(
            "success"
            if validated_insights
            else "completed_with_warnings"
        ),
        agent="Scientific Cross-Paper Synthesis Agent",
        total_papers_received=len(request.evidence_reports),
        total_papers_used=len(usable_reports),
        total_evidence_items=len(evidence_payload),
        total_insights=len(validated_insights),
        insights=validated_insights,
        warnings=warnings,
    )
