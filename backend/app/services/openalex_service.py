

import httpx

from app.schemas.paper import Paper


OPENALEX_URL = "https://api.openalex.org/works"


def reconstruct_abstract(inverted_index):
    """
    Convert OpenAlex's inverted abstract index
    into normal readable text.
    """

    if not inverted_index:
        return None

    words = []

    for word, positions in inverted_index.items():
        for position in positions:
            words.append((position, word))

    words.sort(key=lambda item: item[0])

    return " ".join(word for position, word in words)


def search_openalex(keyword: str, limit: int = 5) -> list[Paper]:

    params = {
        "search": keyword,
        "per_page": limit,
        "select": (
            "id,doi,title,publication_year,"
            "authorships,abstract_inverted_index,"
            "primary_location"
        )
    }

    try:
        response = httpx.get(
            OPENALEX_URL,
            params=params,
            timeout=30.0
        )

        response.raise_for_status()

        data = response.json()

        papers = []

        for item in data.get("results", []):

            authors = []

            for authorship in item.get("authorships", [])[:5]:
                author = authorship.get("author", {})

                if author.get("display_name"):
                    authors.append(author["display_name"])

            abstract = reconstruct_abstract(
                item.get("abstract_inverted_index")
            )

            doi = item.get("doi")

            primary_location = item.get("primary_location") or {}
            landing_page = primary_location.get("landing_page_url")

            paper_url = (
                doi
                or landing_page
                or item.get("id")
            )

            paper = Paper(
                paper_id=item.get("id", ""),
                title=item.get("title") or "Untitled",
                authors=authors,
                publication_year=item.get("publication_year"),
                abstract=abstract,
                doi=doi,
                source="OpenAlex",
                paper_url=paper_url
            )

            papers.append(paper)

        return papers

    except httpx.HTTPError as error:
        print(f"OpenAlex API Error: {error}")
        return []