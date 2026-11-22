import re

# Keep the source text comfortably below the provider prompt limit.
# Evidence-extraction instructions and paper metadata add overhead.
MAX_CHUNK_CHARS = 4500


def split_document_into_pages(full_text: str) -> list[tuple[int, str]]:
    """
    Recover page numbers from the markers created
    by the Phase 4 PDF extraction service.
    """
    pattern = r"--- PAGE (\\d+) ---"
    matches = list(re.finditer(pattern, full_text))

    if not matches:
        return [(1, full_text)] if full_text.strip() else []

    pages = []

    for index, match in enumerate(matches):
        start = match.end()
        end = (
            matches[index + 1].start()
            if index + 1 < len(matches)
            else len(full_text)
        )

        page_number = int(match.group(1))
        page_text = full_text[start:end].strip()

        if page_text:
            pages.append((page_number, page_text))

    return pages


def split_large_page(
    page_number: int,
    page_text: str
) -> list[tuple[int, str]]:
    """
    Split unusually large pages while preserving
    their original page number.
    """
    if len(page_text) <= MAX_CHUNK_CHARS:
        return [(page_number, page_text)]

    chunks = []
    paragraphs = page_text.split("\\n")
    current_chunk = ""

    for paragraph in paragraphs:
        if (
            current_chunk
            and len(current_chunk) + len(paragraph) + 1 > MAX_CHUNK_CHARS
        ):
            chunks.append((page_number, current_chunk))
            current_chunk = ""

        while len(paragraph) > MAX_CHUNK_CHARS:
            if current_chunk:
                chunks.append((page_number, current_chunk))
                current_chunk = ""

            chunks.append((page_number, paragraph[:MAX_CHUNK_CHARS]))
            paragraph = paragraph[MAX_CHUNK_CHARS:]

        current_chunk += (
            "\\n" + paragraph if current_chunk else paragraph
        )

    if current_chunk:
        chunks.append((page_number, current_chunk))

    return chunks


def create_document_chunks(full_text: str) -> list[dict]:
    pages = split_document_into_pages(full_text)
    page_sections = []

    for page_number, page_text in pages:
        page_sections.extend(
            split_large_page(page_number, page_text)
        )

    chunks = []
    current_pages = []
    current_length = 0

    for page_number, page_text in page_sections:
        if (
            current_pages
            and current_length + len(page_text) > MAX_CHUNK_CHARS
        ):
            chunks.append(current_pages)
            current_pages = []
            current_length = 0

        current_pages.append({
            "page_number": page_number,
            "text": page_text
        })
        current_length += len(page_text)

    if current_pages:
        chunks.append(current_pages)

    return chunks
