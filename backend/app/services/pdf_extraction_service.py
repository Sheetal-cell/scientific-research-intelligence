
from pathlib import Path
import pymupdf as fitz

def extract_pdf_text(pdf_path: str) -> dict:

    pdf_file = Path(pdf_path)

    if not pdf_file.exists():
        raise FileNotFoundError("PDF file does not exist.")

    document = fitz.open(pdf_file)

    extracted_pages = []

    try:
        page_count = len(document)

        for page_number, page in enumerate(document, start=1):

            page_text = page.get_text("text")

            extracted_pages.append(
                f"\n\n--- PAGE {page_number} ---\n\n"
                f"{page_text.strip()}"
            )

        full_text = "\n".join(extracted_pages).strip()

        text_path = pdf_file.with_suffix(".txt")

        text_path.write_text(
            full_text,
            encoding="utf-8"
        )

        return {
            "page_count": page_count,
            "extracted_chars": len(full_text),
            "text_path": str(text_path),
            "text": full_text
        }

    finally:
        document.close()