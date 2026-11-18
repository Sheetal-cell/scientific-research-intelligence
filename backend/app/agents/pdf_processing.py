
from app.schemas.paper import Paper
from app.schemas.document import (
    PaperDocument,
    PDFProcessingResponse,
)

from app.services.pdf_service import download_pdf
from app.services.pdf_extraction_service import extract_pdf_text

def process_research_papers(
    papers: list[Paper]
) -> PDFProcessingResponse:

    results = []

    successful_downloads = 0
    successful_extractions = 0

    for paper in papers:

        pdf_path, download_message = download_pdf(
            paper.paper_id
        )

        if not pdf_path:

            results.append(
                PaperDocument(
                    paper_id=paper.paper_id,
                    title=paper.title,
                    download_status="failed",
                    extraction_status="not_started",
                    message=download_message
                )
            )

            continue

        successful_downloads += 1

        try:

            extracted = extract_pdf_text(pdf_path)

            if extracted["extracted_chars"] == 0:

                results.append(
                    PaperDocument(
                        paper_id=paper.paper_id,
                        title=paper.title,
                        download_status="success",
                        extraction_status="no_extractable_text",
                        page_count=extracted["page_count"],
                        extracted_chars=0,
                        pdf_path=pdf_path,
                        text_path=extracted["text_path"],
                        message=(
                            "PDF downloaded, but no selectable text "
                            "was found. OCR may be required."
                        )
                    )
                )

                continue

            successful_extractions += 1

            results.append(
                PaperDocument(
                    paper_id=paper.paper_id,
                    title=paper.title,
                    download_status="success",
                    extraction_status="success",
                    page_count=extracted["page_count"],
                    extracted_chars=extracted["extracted_chars"],
                    pdf_path=pdf_path,
                    text_path=extracted["text_path"],
                    text_preview=extracted["text"][:2000],
                    message="PDF downloaded and text extracted successfully."
                )
            )

        except Exception as error:

            print(
                f"PDF Extraction Error for {paper.paper_id}: {error}"
            )

            results.append(
                PaperDocument(
                    paper_id=paper.paper_id,
                    title=paper.title,
                    download_status="success",
                    extraction_status="failed",
                    pdf_path=pdf_path,
                    message="PDF was downloaded, but text extraction failed."
                )
            )

    return PDFProcessingResponse(
        status="success",
        agent="Research PDF Collection and Extraction Agent",
        total_papers_received=len(papers),
        successful_downloads=successful_downloads,
        successful_extractions=successful_extractions,
        results=results
    )