
import hashlib
import ipaddress
import re

from pathlib import Path
from urllib.parse import urlparse

import httpx

BASE_DIR = Path(__file__).resolve().parents[2]
PAPER_DIR = BASE_DIR / "data" / "papers"

PAPER_DIR.mkdir(parents=True, exist_ok=True)

OPENALEX_URL = "https://api.openalex.org/works"

MAX_PDF_SIZE = 30 * 1024 * 1024  # 30 MB

def get_safe_filename(paper_id: str) -> str:
    """
    Create a stable filename without using untrusted
    paper IDs directly as filesystem paths.
    """
    return hashlib.sha256(
        paper_id.encode("utf-8")
    ).hexdigest()[:24]

def is_safe_pdf_url(url: str) -> bool:
    """
    Allow HTTPS URLs and reject localhost/private IP addresses.
    """
    try:
        parsed = urlparse(url)

        if parsed.scheme != "https" or not parsed.hostname:
            return False

        host = parsed.hostname.lower()

        if host == "localhost" or host.endswith(".localhost"):
            return False

        try:
            address = ipaddress.ip_address(host)

            if not address.is_global:
                return False

        except ValueError:
            pass

        return True

    except Exception:
        return False

def get_arxiv_pdf_url(paper_id: str) -> str | None:
    if not paper_id.startswith("arxiv:"):
        return None

    arxiv_id = paper_id.replace("arxiv:", "", 1)

    if not re.fullmatch(r"[A-Za-z0-9.]+(?:v[0-9]+)?", arxiv_id):
        return None

    return f"https://arxiv.org/pdf/{arxiv_id}"

def get_openalex_pdf_url(paper_id: str) -> str | None:
    """
    Ask OpenAlex for the work's open-access PDF location.
    This does not attempt to access paid publisher PDFs.
    """
    if "openalex.org/" not in paper_id:
        return None

    work_id = paper_id.rstrip("/").split("/")[-1]

    if not re.fullmatch(r"W[0-9]+", work_id):
        return None

    try:
        response = httpx.get(
            f"{OPENALEX_URL}/{work_id}",
            timeout=30.0
        )

        response.raise_for_status()
        data = response.json()

        best_location = data.get("best_oa_location") or {}
        pdf_url = best_location.get("pdf_url")

        if pdf_url and is_safe_pdf_url(pdf_url):
            return pdf_url

        for location in data.get("locations", []):
            pdf_url = location.get("pdf_url")

            if pdf_url and is_safe_pdf_url(pdf_url):
                return pdf_url

        return None

    except (httpx.HTTPError, ValueError) as error:
        print(f"OpenAlex PDF lookup failed: {error}")
        return None

def find_pdf_url(paper_id: str) -> str | None:

    arxiv_url = get_arxiv_pdf_url(paper_id)

    if arxiv_url:
        return arxiv_url

    return get_openalex_pdf_url(paper_id)

def download_pdf(paper_id: str) -> tuple[str | None, str]:

    pdf_url = find_pdf_url(paper_id)

    if not pdf_url:
        return None, "No openly accessible PDF found."

    if not is_safe_pdf_url(pdf_url):
        return None, "The PDF URL failed the security check."

    filename = get_safe_filename(paper_id)
    pdf_path = PAPER_DIR / f"{filename}.pdf"
    temporary_path = PAPER_DIR / f"{filename}.tmp"

    try:
        total_size = 0

        with httpx.stream(
            "GET",
            pdf_url,
            timeout=60.0,
            follow_redirects=True,
            headers={
                "User-Agent": "ScientificResearchIntelligence/1.0"
            }
        ) as response:

            response.raise_for_status()

            if not is_safe_pdf_url(str(response.url)):
                return None, "The final PDF URL failed the security check."

            content_length = response.headers.get("content-length")

            if content_length and int(content_length) > MAX_PDF_SIZE:
                return None, "PDF exceeds the 30 MB size limit."

            with open(temporary_path, "wb") as file:

                for chunk in response.iter_bytes():

                    total_size += len(chunk)

                    if total_size > MAX_PDF_SIZE:
                        return None, "PDF exceeds the 30 MB size limit."

                    file.write(chunk)

        with open(temporary_path, "rb") as file:
            signature = file.read(5)

        if signature != b"%PDF-":
            return None, "The downloaded resource is not a valid PDF."

        temporary_path.replace(pdf_path)

        return str(pdf_path), "PDF downloaded successfully."

    except (httpx.HTTPError, OSError, ValueError) as error:
        print(f"PDF Download Error: {error}")
        return None, "PDF download failed."

    finally:
        if temporary_path.exists():
            temporary_path.unlink()