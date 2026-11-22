"""Resilient end-to-end research orchestration.

Individual agents remain independently callable. The website uses this
orchestrator and receives a structured response even when an external
provider or a later pipeline stage is unavailable.
"""
import traceback
from pathlib import Path

from app.agents.research_planner import create_research_plan
from app.agents.paper_discovery import discover_papers
from app.agents.paper_filter import filter_research_papers
from app.agents.pdf_processing import process_research_papers
from app.agents.evidence_extraction import extract_research_evidence
from app.agents.cross_paper_synthesis import synthesize_research
from app.agents.report_generation import generate_research_report
from app.agents.research_quality import evaluate_research_report

from app.schemas.workflow import ResearchWorkflowResponse, WorkflowStage
from app.schemas.paper import PaperFilteringRequest
from app.schemas.evidence import EvidenceExtractionRequest
from app.schemas.synthesis import SynthesisRequest, CrossPaperSynthesisResponse
from app.schemas.report import ResearchReportRequest
from app.schemas.quality import (
    ReportQualityRequest,
    ReportQualityResponse,
    SectionQualityResult,
)
from app.schemas.export import ResearchPDFExportRequest
from app.services.pdf_report_service import generate_research_pdf


def _stage(stages, name, status, message, metrics=None):
    stages.append(WorkflowStage(
        name=name,
        status=status,
        message=message,
        metrics=metrics or {},
    ))


def _stop(question, title, stages, **results):
    """Return everything completed so far instead of losing it to an HTTP error."""
    return ResearchWorkflowResponse(
        status="failed",
        research_title=title or question[:120] or "Research investigation",
        stages=stages,
        **results,
    )


def _fallback_quality(report, reason):
    """Clearly mark AI quality review as unavailable; never fabricate a score."""
    sections = [
        SectionQualityResult(
            section_title=section.title,
            verdict="unsupported",
            score=0,
            issues=["AI quality evaluation did not complete; this is not a scientific verdict."],
            comparability_concerns=[],
            verified_citations=0,
            invalid_citations=0,
        )
        for section in report.sections
    ]
    return ReportQualityResponse(
        status="completed_with_warnings",
        agent="Scientific Research Quality Evaluation Agent",
        overall_score=0,
        citation_integrity_score=0,
        total_citations_checked=0,
        verified_citations=0,
        invalid_citations=0,
        sections_evaluated=len(sections),
        sections=sections,
        citation_checks=[],
        warnings=[
            "AI quality evaluation was unavailable. No citation verification score is claimed.",
            reason,
        ],
    )


def run_research_workflow(question: str):
    stages = []
    title = question[:120]

    # 1. Planning
    try:
        plan = create_research_plan(question)
        title = plan.research_title
        _stage(stages, "Research Planning", "success",
               "Research question converted into structured tasks.",
               {"tasks_created": len(plan.tasks)})
        if not plan.tasks:
            _stage(stages, "Research Planning", "failed",
                   "The planner returned no research tasks.")
            return _stop(question, title, stages)
    except Exception as error:
        traceback.print_exc()
        _stage(stages, "Research Planning", "failed",
               f"Research planning failed: {error}")
        return _stop(question, title, stages)

    # 2. Discovery
    try:
        discovery_results = discover_papers(plan.tasks)
        total_discovered = sum(item.total_found for item in discovery_results)
        _stage(stages, "Paper Discovery",
               "success" if total_discovered else "failed",
               f"Discovered {total_discovered} papers.",
               {"papers_found": total_discovered,
                "tasks_searched": len(discovery_results)})
        if not total_discovered:
            return _stop(question, title, stages, research_plan=plan)
    except Exception as error:
        traceback.print_exc()
        _stage(stages, "Paper Discovery", "failed",
               f"Paper discovery failed: {error}")
        return _stop(question, title, stages, research_plan=plan)

    # 3. Relevance filtering
    try:
        filtering = filter_research_papers(
            PaperFilteringRequest(tasks=plan.tasks, results=discovery_results)
        )
        relevant_papers = []
        seen_ids = set()
        for task_result in filtering.results:
            for item in task_result.papers:
                paper_id = item.paper.paper_id
                if item.relevant and paper_id not in seen_ids:
                    relevant_papers.append(item.paper)
                    seen_ids.add(paper_id)

        _stage(stages, "Relevance Filtering",
               "success" if len(relevant_papers) >= 2 else "failed",
               f"{len(relevant_papers)} relevant unique papers selected.",
               {"evaluated": filtering.total_papers_evaluated,
                "relevant": len(relevant_papers),
                "threshold": filtering.relevance_threshold})
        if len(relevant_papers) < 2:
            return _stop(question, title, stages,
                         research_plan=plan, filtering=filtering)
    except Exception as error:
        traceback.print_exc()
        _stage(stages, "Relevance Filtering", "failed",
               f"Paper relevance assessment failed: {error}")
        return _stop(question, title, stages, research_plan=plan)

    # 4. PDF collection and extraction
    try:
        pdf_processing = process_research_papers(relevant_papers)
        extracted_ids = {
            item.paper_id for item in pdf_processing.results
            if item.extraction_status == "success"
        }
        extracted_papers = [
            paper for paper in relevant_papers
            if paper.paper_id in extracted_ids
        ]
        _stage(stages, "PDF Collection and Extraction",
               "success" if len(extracted_papers) >= 2 else "failed",
               f"Successfully extracted text from {len(extracted_papers)} papers.",
               {"received": len(relevant_papers),
                "downloaded": pdf_processing.successful_downloads,
                "extracted": pdf_processing.successful_extractions})
        if len(extracted_papers) < 2:
            reasons = [
                f"{item.title}: {item.message or item.extraction_status}"
                for item in pdf_processing.results
                if item.extraction_status != "success"
            ]
            stages[-1].metrics["failed_papers"] = reasons[:8]
            return _stop(question, title, stages,
                         research_plan=plan, filtering=filtering,
                         pdf_processing=pdf_processing)
    except Exception as error:
        traceback.print_exc()
        _stage(stages, "PDF Collection and Extraction", "failed",
               f"PDF processing failed: {error}")
        return _stop(question, title, stages,
                     research_plan=plan, filtering=filtering)

    # 5. Evidence extraction
    try:
        evidence_extraction = extract_research_evidence(
            EvidenceExtractionRequest(papers=extracted_papers)
        )
        usable_reports = [
            item for item in evidence_extraction.results
            if item.extraction_status in ("success", "partial") and item.evidence
        ]
        _stage(stages, "Scientific Evidence Extraction",
               "success" if len(usable_reports) >= 2 else "failed",
               f"Extracted usable evidence from {len(usable_reports)} papers.",
               {"papers_received": evidence_extraction.total_papers_received,
                "successful": evidence_extraction.successfully_analyzed,
                "partial": evidence_extraction.partially_analyzed,
                "failed": evidence_extraction.failed})
        if len(usable_reports) < 2:
            return _stop(question, title, stages,
                         research_plan=plan, filtering=filtering,
                         pdf_processing=pdf_processing,
                         evidence_extraction=evidence_extraction)
    except Exception as error:
        traceback.print_exc()
        _stage(stages, "Scientific Evidence Extraction", "failed",
               f"Evidence extraction failed: {error}")
        return _stop(question, title, stages,
                     research_plan=plan, filtering=filtering,
                     pdf_processing=pdf_processing)

    # 6. Synthesis is useful but should not prevent an evidence-based report.
    try:
        synthesis = synthesize_research(
            SynthesisRequest(evidence_reports=usable_reports)
        )
        _stage(stages, "Cross-Paper Synthesis", synthesis.status,
               f"Generated {synthesis.total_insights} validated cross-paper insights.",
               {"papers_used": synthesis.total_papers_used,
                "evidence_items": synthesis.total_evidence_items,
                "insights": synthesis.total_insights})
    except Exception as error:
        traceback.print_exc()
        synthesis = CrossPaperSynthesisResponse(
            status="completed_with_warnings",
            agent="Scientific Cross-Paper Synthesis Agent",
            total_papers_received=len(usable_reports),
            total_papers_used=len(usable_reports),
            total_evidence_items=sum(len(item.evidence) for item in usable_reports),
            total_insights=0,
            insights=[],
            warnings=[f"Cross-paper synthesis was unavailable: {error}"],
        )
        _stage(stages, "Cross-Paper Synthesis", "warning",
               "Synthesis was unavailable. Continuing with individually extracted evidence.",
               {"reason": str(error)})

    # 7. Report generation
    try:
        report = generate_research_report(
            ResearchReportRequest(
                research_plan=plan,
                evidence_reports=usable_reports,
                synthesis=synthesis,
            )
        )
        _stage(stages, "Research Report Generation", report.status,
               "Scientific research report generated.",
               {"sections": len(report.sections),
                "citations": report.total_citations,
                "papers_used": report.total_papers_used})
    except Exception as error:
        traceback.print_exc()
        _stage(stages, "Research Report Generation", "failed",
               f"Report generation failed: {error}")
        return _stop(question, title, stages,
                     research_plan=plan, filtering=filtering,
                     pdf_processing=pdf_processing,
                     evidence_extraction=evidence_extraction,
                     synthesis=synthesis)

    # 8. Quality evaluation. Preserve the report if the evaluator is down.
    try:
        quality = evaluate_research_report(
            ReportQualityRequest(report=report, evidence_reports=usable_reports)
        )
        _stage(stages, "Citation and Quality Evaluation", quality.status,
               "Report citation integrity and section quality evaluated.",
               {"overall_score": quality.overall_score,
                "citation_integrity": quality.citation_integrity_score,
                "citations_checked": quality.total_citations_checked,
                "verified": quality.verified_citations,
                "invalid": quality.invalid_citations})
    except Exception as error:
        traceback.print_exc()
        quality = _fallback_quality(report, str(error))
        _stage(stages, "Citation and Quality Evaluation", "warning",
               "The report is ready, but AI quality evaluation was unavailable.",
               {"reason": str(error)})

    # 9. PDF export. A PDF failure must not hide the completed web report.
    pdf_filename = None
    try:
        export_request = ResearchPDFExportRequest.model_validate({
            "report": report.model_dump(),
            "quality_evaluation": quality.model_dump(),
        })
        export_result = generate_research_pdf(export_request)
        pdf_filename = Path(export_result["file_path"]).name
        _stage(stages, "PDF Report Export", "success",
               "Final research report PDF generated.",
               {"filename": pdf_filename})
    except Exception as error:
        traceback.print_exc()
        _stage(stages, "PDF Report Export", "warning",
               f"The web report is ready, but PDF export failed: {error}")

    has_warnings = any(stage.status != "success" for stage in stages)
    return ResearchWorkflowResponse(
        status="completed_with_warnings" if has_warnings else "success",
        research_title=title,
        stages=stages,
        research_plan=plan,
        filtering=filtering,
        pdf_processing=pdf_processing,
        evidence_extraction=evidence_extraction,
        synthesis=synthesis,
        report=report,
        quality_evaluation=quality,
        pdf_filename=pdf_filename,
    )
