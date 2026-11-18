
import os
import re
import uuid
import unicodedata

from datetime import datetime, timezone
from xml.sax.saxutils import escape

from reportlab.lib import colors # type: ignore
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY # pyright: ignore[reportMissingModuleSource]
from reportlab.lib.pagesizes import A4  # pyright: ignore[reportMissingModuleSource]
from reportlab.lib.styles import (  # pyright: ignore[reportMissingModuleSource]
    getSampleStyleSheet,
    ParagraphStyle,
)
from reportlab.lib.units import mm # pyright: ignore[reportMissingModuleSource]

from reportlab.platypus import ( # pyright: ignore[reportMissingModuleSource]
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    KeepTogether,
)

from app.schemas.export import ResearchPDFExportRequest

BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
)

REPORT_DIR = os.path.join(
    BASE_DIR,
    "data",
    "reports"
)

os.makedirs(REPORT_DIR, exist_ok=True)

def safe_text(value):
    """
    Convert text into PDF-safe ASCII text.
    This avoids encoding errors with built-in PDF fonts.
    """
    value = str(value or "")

    replacements = {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "-",
        "\u2022": "-",
        "\u00a0": " ",
    }

    for old, new in replacements.items():
        value = value.replace(old, new)

    value = unicodedata.normalize("NFKD", value)

    return value.encode(
        "ascii",
        "ignore"
    ).decode("ascii")

def safe_paragraph(text):
    """
    Escape content before passing it to ReportLab Paragraph.
    """
    text = safe_text(text)
    text = escape(text)
    text = text.replace("\n", "<br/>")

    return text

def make_filename(title):
    title = safe_text(title).lower()

    title = re.sub(
        r"[^a-z0-9]+",
        "-",
        title
    )

    title = title.strip("-")[:60]

    if not title:
        title = "research-report"

    return (
        f"{title}-"
        f"{uuid.uuid4().hex[:8]}.pdf"
    )

def create_styles():

    styles = getSampleStyleSheet()

    styles.add(
        ParagraphStyle(
            name="ReportTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=23,
            leading=30,
            alignment=TA_CENTER,
            spaceAfter=18,
        )
    )

    styles.add(
        ParagraphStyle(
            name="Subtitle",
            parent=styles["Normal"],
            fontSize=11,
            leading=17,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#555555"),
        )
    )

    styles.add(
        ParagraphStyle(
            name="SectionHeading",
            parent=styles["Heading2"],
            fontSize=15,
            leading=20,
            spaceBefore=15,
            spaceAfter=9,
            textColor=colors.HexColor("#17365D"),
        )
    )

    styles.add(
        ParagraphStyle(
            name="BodyTextCustom",
            parent=styles["BodyText"],
            fontSize=9.5,
            leading=15,
            alignment=TA_JUSTIFY,
            spaceAfter=9,
        )
    )

    styles.add(
        ParagraphStyle(
            name="SmallText",
            parent=styles["BodyText"],
            fontSize=8,
            leading=11,
            spaceAfter=4,
        )
    )

    styles.add(
        ParagraphStyle(
            name="CitationHeading",
            parent=styles["Heading3"],
            fontSize=10,
            leading=13,
            spaceBefore=8,
            spaceAfter=5,
            textColor=colors.HexColor("#24476B"),
        )
    )

    styles.add(
        ParagraphStyle(
            name="WarningText",
            parent=styles["BodyText"],
            fontSize=8.5,
            leading=12,
            textColor=colors.HexColor("#9C3B20"),
            spaceAfter=5,
        )
    )

    return styles

def draw_page(canvas, doc):

    canvas.saveState()

    page_width, page_height = A4

    canvas.setFont("Helvetica", 8)

    canvas.setFillColor(
        colors.HexColor("#666666")
    )

    canvas.drawString(
        20 * mm,
        12 * mm,
        "Scientific Research Intelligence"
    )

    canvas.drawRightString(
        page_width - 20 * mm,
        12 * mm,
        f"Page {doc.page}"
    )

    canvas.restoreState()

def add_citation_section(story, section, styles):

    citations = section.citations

    if not citations:
        story.append(
            Paragraph(
                "<b>Citations:</b> No citations attached.",
                styles["SmallText"]
            )
        )
        return

    story.append(
        Paragraph(
            "Supporting References",
            styles["CitationHeading"]
        )
    )

    for index, citation in enumerate(citations, start=1):

        citation_text = (
            f"<b>[{index}] "
            f"{safe_paragraph(citation.paper_title)}</b><br/>"
            f"Paper ID: {safe_paragraph(citation.paper_id)}<br/>"
            f"Evidence ID: {safe_paragraph(citation.evidence_id)}<br/>"
            f"Category: {safe_paragraph(citation.category)}"
            f" | Page: {citation.page_number}<br/>"
            f"<b>Finding:</b> "
            f"{safe_paragraph(citation.finding)}<br/>"
            f"<b>Supporting excerpt:</b> "
            f"{safe_paragraph(citation.supporting_excerpt)}"
        )

        story.append(
            Paragraph(
                citation_text,
                styles["SmallText"]
            )
        )

        story.append(Spacer(1, 4))

def add_quality_summary(story, quality, styles):

    story.append(PageBreak())

    story.append(
        Paragraph(
            "Research Quality Evaluation",
            styles["SectionHeading"]
        )
    )

    story.append(
        Paragraph(
            "This evaluation was generated by the "
            "Scientific Research Quality Evaluation Agent. "
            "Citation checks and AI-based section assessments "
            "are reported separately from the research findings.",
            styles["BodyTextCustom"]
        )
    )

    summary_data = [
        ["Quality Metric", "Result"],
        ["Overall Score", f"{quality.overall_score}/100"],
        [
            "Citation Integrity",
            f"{quality.citation_integrity_score}/100"
        ],
        [
            "Citations Checked",
            str(quality.total_citations_checked)
        ],
        [
            "Verified Citations",
            str(quality.verified_citations)
        ],
        [
            "Invalid Citations",
            str(quality.invalid_citations)
        ],
        [
            "Sections Evaluated",
            str(quality.sections_evaluated)
        ],
    ]

    summary_table = Table(
        summary_data,
        colWidths=[75 * mm, 75 * mm]
    )

    summary_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0),
             colors.HexColor("#17365D")),
            ("TEXTCOLOR", (0, 0), (-1, 0),
             colors.white),
            ("FONTNAME", (0, 0), (-1, 0),
             "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.5,
             colors.HexColor("#CCCCCC")),
            ("BACKGROUND", (0, 1), (-1, -1),
             colors.HexColor("#F5F7FA")),
            ("FONTNAME", (0, 1), (0, -1),
             "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("PADDING", (0, 0), (-1, -1), 8),
        ])
    )

    story.append(summary_table)
    story.append(Spacer(1, 14))

    story.append(
        Paragraph(
            "Section-wise Quality Assessment",
            styles["CitationHeading"]
        )
    )

    for section in quality.sections:

        details = (
            f"<b>{safe_paragraph(section.section_title)}</b><br/>"
            f"Verdict: {safe_paragraph(section.verdict)}"
            f" | Score: {section.score}/100<br/>"
            f"Verified citations: {section.verified_citations}"
            f" | Invalid citations: {section.invalid_citations}"
        )

        story.append(
            Paragraph(details, styles["SmallText"])
        )

        for issue in section.issues:

            story.append(
                Paragraph(
                    f"Issue: {safe_paragraph(issue)}",
                    styles["WarningText"]
                )
            )

        for concern in section.comparability_concerns:

            story.append(
                Paragraph(
                    f"Comparability concern: "
                    f"{safe_paragraph(concern)}",
                    styles["SmallText"]
                )
            )

        story.append(Spacer(1, 5))

def add_citation_verification(story, quality, styles):

    story.append(
        Paragraph(
            "Citation Verification Details",
            styles["SectionHeading"]
        )
    )

    if not quality.citation_checks:

        story.append(
            Paragraph(
                "No citation verification records were provided.",
                styles["SmallText"]
            )
        )
        return

    for index, check in enumerate(
        quality.citation_checks,
        start=1
    ):

        status = safe_paragraph(check.status)

        details = (
            f"<b>{index}. {status}</b><br/>"
            f"Paper ID: {safe_paragraph(check.paper_id)}<br/>"
            f"Evidence ID: {safe_paragraph(check.evidence_id)}<br/>"
            f"Page: {check.page_number}<br/>"
            f"Citation exists: {check.citation_exists}"
            f" | Page matches: {check.page_matches}"
            f" | Excerpt verified: {check.excerpt_verified}<br/>"
            f"Message: {safe_paragraph(check.message)}"
        )

        story.append(
            Paragraph(
                details,
                styles["SmallText"]
            )
        )

        story.append(Spacer(1, 5))

def add_warnings(story, warnings, styles):

    story.append(
        Paragraph(
            "Warnings and Review Notes",
            styles["SectionHeading"]
        )
    )

    if not warnings:

        story.append(
            Paragraph(
                "No warnings were reported by the quality evaluator.",
                styles["SmallText"]
            )
        )
        return

    for warning in warnings:

        story.append(
            Paragraph(
                f"- {safe_paragraph(warning)}",
                styles["WarningText"]
            )
        )

def generate_research_pdf(
    request: ResearchPDFExportRequest
):

    report = request.report
    quality = request.quality_evaluation

    filename = make_filename(
        report.research_title
    )

    file_path = os.path.join(
        REPORT_DIR,
        filename
    )

    styles = create_styles()

    document = SimpleDocTemplate(
        file_path,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        title=safe_text(report.research_title),
        author="Scientific Research Intelligence",
    )

    story = []

    # TITLE PAGE
    story.append(Spacer(1, 45 * mm))

    story.append(
        Paragraph(
            safe_paragraph(report.research_title),
            styles["ReportTitle"]
        )
    )

    story.append(
        Paragraph(
            "Scientific Research Intelligence",
            styles["Subtitle"]
        )
    )

    story.append(Spacer(1, 15 * mm))

    story.append(
        Paragraph(
            "AI-Assisted Scientific Literature Review",
            styles["Subtitle"]
        )
    )

    story.append(Spacer(1, 10 * mm))

    story.append(
        Paragraph(
            f"Generated on: "
            f"{datetime.now(timezone.utc).strftime('%d %B %Y')}",
            styles["Subtitle"]
        )
    )

    story.append(
        Paragraph(
            f"Papers analyzed: {report.total_papers_used}",
            styles["Subtitle"]
        )
    )

    story.append(PageBreak())

    # EXECUTIVE SUMMARY
    story.append(
        Paragraph(
            "Executive Summary",
            styles["SectionHeading"]
        )
    )

    story.append(
        Paragraph(
            safe_paragraph(report.executive_summary),
            styles["BodyTextCustom"]
        )
    )

    # REPORT SECTIONS
    for section in report.sections:

        section_content = []

        section_content.append(
            Paragraph(
                safe_paragraph(section.title),
                styles["SectionHeading"]
            )
        )

        section_content.append(
            Paragraph(
                safe_paragraph(section.content),
                styles["BodyTextCustom"]
            )
        )

        story.append(
            KeepTogether(section_content)
        )

        add_citation_section(
            story,
            section,
            styles
        )

    # FINAL CONCLUSION
    story.append(
        Paragraph(
            "Overall Conclusion",
            styles["SectionHeading"]
        )
    )

    story.append(
        Paragraph(
            safe_paragraph(report.overall_conclusion),
            styles["BodyTextCustom"]
        )
    )

    # PHASE 8 QUALITY EVALUATION
    add_quality_summary(
        story,
        quality,
        styles
    )

    add_citation_verification(
        story,
        quality,
        styles
    )

    add_warnings(
        story,
        quality.warnings,
        styles
    )

    # BUILD PDF
    document.build(
        story,
        onFirstPage=draw_page,
        onLaterPages=draw_page
    )

    return {
        "filename": filename,
        "file_path": file_path,
        "report_title": report.research_title,
    }