import os
import random
import time

import httpx

from app.schemas.paper import Paper

OPENALEX_URL = "https://api.openalex.org/works"
REQUEST_TIMEOUT = 25.0
MAX_ATTEMPTS = 4


def reconstruct_abstract(inverted_index):
    """Rebuild OpenAlex's inverted abstract index into readable text."""
    if not inverted_index:
        return None

    words = []
    for word, positions in inverted_index.items():
        for position in positions:
            words.append((position, word))

    words.sort(key=lambda item: item[0])
    return " ".join(word for _, word in words)


def _request_headers():
    headers = {"User-Agent": "ScientificResearchIntelligence/1.0 (mailto:research@example.com)"}
    mailto = os.getenv("OPENALEX_MAILTO")
    if mailto:
        headers["User-Agent"] = f"ScientificResearchIntelligence/1.0 (mailto:{mailto})"
    return headers


def search_openalex(keyword: str, limit: int = 5) -> list[Paper]:
    """Search OpenAlex with bounded retry/backoff for rate limits and transient errors."""
    params = {
        "search": keyword,
        "per_page": max(1, min(int(limit), 25)),
        "select": "id,doi,title,publication_year,authorships,abstract_inverted_index,primary_location",
    }

    for attempt in range(MAX_ATTEMPTS):
        try:
            with httpx.Client(timeout=REQUEST_TIMEOUT, headers=_request_headers()) as client:
                response = client.get(OPENALEX_URL, params=params)

            if response.status_code == 429 or response.status_code in (500, 502, 503, 504):
                if attempt == MAX_ATTEMPTS - 1:
                    response.raise_for_status()
                retry_after = response.headers.get("Retry-After")
                try:
                    wait_seconds = float(retry_after) if retry_after else min(2 ** attempt, 12)
                except ValueError:
                    wait_seconds = min(2 ** attempt, 12)
                time.sleep(wait_seconds + random.uniform(0.1, 0.6))
                continue

            response.raise_for_status()
            data = response.json()
            papers = []

            for item in data.get("results", []):
                authors = []
                for authorship in item.get("authorships", [])[:5]:
                    author = authorship.get("author", {})
                    if author.get("display_name"):
                        authors.append(author["display_name"])

                primary_location = item.get("primary_location") or {}
                paper_url = (
                    item.get("doi")
                    or primary_location.get("landing_page_url")
                    or item.get("id")
                )
                papers.append(
                    Paper(
                        paper_id=item.get("id", ""),
                        title=item.get("title") or "Untitled",
                        authors=authors,
                        publication_year=item.get("publication_year"),
                        abstract=reconstruct_abstract(item.get("abstract_inverted_index")),
                        doi=item.get("doi"),
                        source="OpenAlex",
                        paper_url=paper_url,
                    )
                )
            return papers

        except httpx.HTTPStatusError as error:
            status = error.response.status_code
            print(f"OpenAlex HTTP {status} for query '{keyword}': {error}")
            if status != 429 and status not in (500, 502, 503, 504):
                return []
            if attempt == MAX_ATTEMPTS - 1:
                return []
        except (httpx.HTTPError, ValueError) as error:
            print(f"OpenAlex request failed for query '{keyword}': {error}")
            if attempt == MAX_ATTEMPTS - 1:
                return []
            time.sleep(min(2 ** attempt, 8) + random.uniform(0.1, 0.5))

    return []
