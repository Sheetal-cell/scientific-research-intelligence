import re
import time
import httpx
import xml.etree.ElementTree as ET

from app.schemas.paper import Paper


ARXIV_URL = "https://export.arxiv.org/api/query"

ATOM_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom"
}


def search_arxiv(keyword: str, limit: int = 5) -> list[Paper]:

    params = {
        "search_query": f"all:{keyword}",
        "start": 0,
        "max_results": limit,
        "sortBy": "relevance",
        "sortOrder": "descending"
    }

    try:
        response = httpx.get(
            ARXIV_URL,
            params=params,
            timeout=45.0,
            headers={"User-Agent": "ScientificResearchIntelligence/1.0"}
        )

        response.raise_for_status()

        root = ET.fromstring(response.text)
        papers = []

        entries = root.findall("atom:entry", ATOM_NS)

        for entry in entries:

            arxiv_url = entry.findtext("atom:id", default="", namespaces=ATOM_NS)
            title = entry.findtext("atom:title", default="", namespaces=ATOM_NS)
            abstract = entry.findtext("atom:summary", default="", namespaces=ATOM_NS)

            title = " ".join(title.split())
            abstract = " ".join(abstract.split())

            published = entry.findtext(
                "atom:published", default="", namespaces=ATOM_NS
            )

            publication_year = None

            if published:
                publication_year = int(published[:4])

            authors = []

            for author in entry.findall("atom:author", ATOM_NS):
                name = author.findtext(
                    "atom:name", default="", namespaces=ATOM_NS
                )

                if name:
                    authors.append(name)

            arxiv_id = arxiv_url.rstrip("/").split("/")[-1]

            doi = entry.findtext(
                "arxiv:doi", default=None, namespaces=ATOM_NS
            )

            if doi:
                doi = "https://doi.org/" + doi

            papers.append(
                Paper(
                    paper_id="arxiv:" + arxiv_id,
                    title=title or "Untitled",
                    authors=authors,
                    publication_year=publication_year,
                    abstract=abstract or None,
                    doi=doi,
                    source="arXiv",
                    paper_url=arxiv_url
                )
            )

        return papers

    except (httpx.HTTPError, ET.ParseError, ValueError) as error:
        print(f"arXiv API Error: {error}")
        return []