
from pathlib import Path

from app.agents.research_planner import create_research_plan
from app.agents.paper_discovery import discover_papers
from app.agents.paper_filter import filter_research_papers
from app.agents.pdf_processing import process_research_papers
from app.agents.evidence_extraction import extract_research_evidence
from app.agents.cross_paper_synthesis import synthesize_research
from app.agents.report_generation import generate_research_report
from app.agents.research_quality import evaluate_research_report

from app.schemas.workflow import (
    ResearchWorkflowResponse,
    WorkflowStage,
)

from app.schemas.paper import PaperFilteringRequest
from app.schemas.document import PDFProcessingResponse
from app.schemas.evidence import EvidenceExtractionRequest
from app.schemas.synthesis import SynthesisRequest
from app.schemas.report import ResearchReportRequest
from app.schemas.quality import ReportQualityRequest
from app.schemas.export import ResearchPDFExportRequest

from app.services.pdf_report_service import generate_research_pdf


def run_research_workflow(question: str):

    stages = []

    # --------------------------------------------------
    # PHASE 1: RESEARCH PLANNING
    # --------------------------------------------------

    plan = create_research_plan(question)

    stages.append(
        WorkflowStage(
            name="Research Planning",
            status="success",
            message="Research question converted into structured tasks.",
            metrics={
                "tasks_created": len(plan.tasks)
            }
        )
    )

    # --------------------------------------------------
    # PHASE 2: PAPER DISCOVERY
    # --------------------------------------------------

    discovery_results = discover_papers(plan.tasks)

    total_discovered = sum(
        result.total_found for result in discovery_results
    )

    stages.append(
        WorkflowStage(
            name="Paper Discovery",
            status="success" if total_discovered else "failed",
            message=f"Discovered {total_discovered} papers.",
            metrics={
                "papers_found": total_discovered,
                "tasks_searched": len(discovery_results)
            }
        )
    )

    if total_discovered == 0:
        raise ValueError(
            "No research papers were discovered. "
            "Try a more specific research question."
        )

    # --------------------------------------------------
    # PHASE 3: RELEVANCE FILTERING
    # --------------------------------------------------

    filtering = filter_research_papers(
        PaperFilteringRequest(
            tasks=plan.tasks,
            results=discovery_results
        )
    )

    relevant_papers = []
    seen_paper_ids = set()

    for task_result in filtering.results:
        for item in task_result.papers:

            if (
                item.relevant
                and item.paper.paper_id not in seen_paper_ids
            ):
                relevant_papers.append(item.paper)
                seen_paper_ids.add(item.paper.paper_id)

    stages.append(
        WorkflowStage(
            name="Relevance Filtering",
            status="success" if relevant_papers else "failed",
            message=f"{len(relevant_papers)} relevant unique papers selected.",
            metrics={
                "evaluated": filtering.total_papers_evaluated,
                "relevant": len(relevant_papers),
                "threshold": filtering.relevance_threshold
            }
        )
    )

    if len(relevant_papers) < 2:
        raise ValueError(
            "Fewer than two relevant papers were found. "
            "At least two papers are required for cross-paper synthesis."
        )

    # --------------------------------------------------
    # PHASE 4: PDF DOWNLOAD AND TEXT EXTRACTION
    # --------------------------------------------------

    pdf_processing = process_research_papers(relevant_papers)

    successfully_extracted_ids = {
        item.paper_id
        for item in pdf_processing.results
        if item.extraction_status == "success"
    }

    extracted_papers = [
        paper
        for paper in relevant_papers
        if paper.paper_id in successfully_extracted_ids
    ]

    stages.append(
        WorkflowStage(
            name="PDF Collection and Extraction",
            status=(
                "success"
                if len(extracted_papers) >= 2
                else "failed"
            ),
            message=(
                f"Successfully extracted text from "
                f"{len(extracted_papers)} papers."
            ),
            metrics={
                "received": len(relevant_papers),
                "downloaded": pdf_processing.successful_downloads,
                "extracted": pdf_processing.successful_extractions
            }
        )
    )

    if len(extracted_papers) < 2:
        raise ValueError(
            "Fewer than two papers could be processed successfully. "
            "The research workflow cannot continue."
        )

    # --------------------------------------------------
    # PHASE 5: EVIDENCE EXTRACTION
    # --------------------------------------------------

    evidence_extraction = extract_research_evidence(
        EvidenceExtractionRequest(
            papers=extracted_papers
        )
    )

    usable_evidence_reports = [
        item
        for item in evidence_extraction.results
        if item.extraction_status in ("success", "partial")
        and item.evidence
    ]

    stages.append(
        WorkflowStage(
            name="Scientific Evidence Extraction",
            status=(
                "success"
                if len(usable_evidence_reports) >= 2
                else "failed"
            ),
            message=(
                f"Extracted usable evidence from "
                f"{len(usable_evidence_reports)} papers."
            ),
            metrics={
                "papers_received": evidence_extraction.total_papers_received,
                "successful": evidence_extraction.successfully_analyzed,
                "partial": evidence_extraction.partially_analyzed,
                "failed": evidence_extraction.failed
            }
        )
    )

    if len(usable_evidence_reports) < 2:
        raise ValueError(
            "Usable scientific evidence was extracted from fewer "
            "than two papers."
        )

    # --------------------------------------------------
    # PHASE 6: CROSS-PAPER SYNTHESIS
    # --------------------------------------------------

    synthesis = synthesize_research(
        SynthesisRequest(
            evidence_reports=usable_evidence_reports
        )
    )

    stages.append(
        WorkflowStage(
            name="Cross-Paper Synthesis",
            status=synthesis.status,
            message=(
                f"Generated {synthesis.total_insights} "
                f"validated cross-paper insights."
            ),
            metrics={
                "papers_used": synthesis.total_papers_used,
                "evidence_items": synthesis.total_evidence_items,
                "insights": synthesis.total_insights
            }
        )
    )

    # --------------------------------------------------
    # PHASE 7: REPORT GENERATION
    # --------------------------------------------------

    report = generate_research_report(
        ResearchReportRequest(
            research_plan=plan,
            evidence_reports=usable_evidence_reports,
            synthesis=synthesis
        )
    )

    stages.append(
        WorkflowStage(
            name="Research Report Generation",
            status=report.status,
            message="Scientific research report generated.",
            metrics={
                "sections": len(report.sections),
                "citations": report.total_citations,
                "papers_used": report.total_papers_used
            }
        )
    )

    # --------------------------------------------------
    # PHASE 8: QUALITY EVALUATION
    # --------------------------------------------------

    quality = evaluate_research_report(
        ReportQualityRequest(
            report=report,
            evidence_reports=usable_evidence_reports
        )
    )

    stages.append(
        WorkflowStage(
            name="Citation and Quality Evaluation",
            status=quality.status,
            message="Report citation integrity and section quality evaluated.",
            metrics={
                "overall_score": quality.overall_score,
                "citation_integrity": quality.citation_integrity_score,
                "citations_checked": quality.total_citations_checked,
                "verified": quality.verified_citations,
                "invalid": quality.invalid_citations
            }
        )
    )

    # --------------------------------------------------
    # PHASE 9: PDF EXPORT
    # --------------------------------------------------

    export_request = ResearchPDFExportRequest.model_validate(
        {
            "report": report.model_dump(),
            "quality_evaluation": quality.model_dump()
        }
    )

    export_result = generate_research_pdf(export_request)

    pdf_filename = Path(
        export_result["file_path"]
    ).name

    stages.append(
        WorkflowStage(
            name="PDF Report Export",
            status="success",
            message="Final research report PDF generated.",
            metrics={
                "filename": pdf_filename
            }
        )
    )

    # --------------------------------------------------
    # FINAL WORKFLOW RESPONSE
    # --------------------------------------------------

    has_warnings = any(
        stage.status != "success"
        for stage in stages
    )

    return ResearchWorkflowResponse(
        status=(
            "completed_with_warnings"
            if has_warnings
            else "success"
        ),
        research_title=plan.research_title,
        stages=stages,
        research_plan=plan,
        filtering=filtering,
        pdf_processing=pdf_processing,
        evidence_extraction=evidence_extraction,
        synthesis=synthesis,
        report=report,
        quality_evaluation=quality,
        pdf_filename=pdf_filename
    )
