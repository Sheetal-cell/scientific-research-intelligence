import re
import time

from app.schemas.research import ResearchTask
from app.schemas.paper import PaperSearchResult, Paper
from app.services.openalex_service import search_openalex
from app.services.arxiv_service import search_arxiv


def normalize_title(title: str) -> str:
    title = title.lower()
    title = re.sub(r"[^a-z0-9]", "", title)
    return title


def normalize_doi(doi: str | None) -> str | None:
    if not doi:
        return None

    doi = doi.lower().strip()
    doi = doi.replace("https://doi.org/", "")
    doi = doi.replace("http://doi.org/", "")
    doi = doi.replace("doi:", "")

    return doi


def merge_papers(papers: list[Paper]) -> list[Paper]:

    unique_papers = {}
    doi_lookup = {}
    title_lookup = {}

    for paper in papers:

        doi_key = normalize_doi(paper.doi)
        title_key = normalize_title(paper.title)

        existing_key = None

        if doi_key and doi_key in doi_lookup:
            existing_key = doi_lookup[doi_key]

        elif title_key and title_key in title_lookup:
            existing_key = title_lookup[title_key]

        if existing_key is None:

            key = paper.paper_id
            unique_papers[key] = paper

            if doi_key:
                doi_lookup[doi_key] = key

            if title_key:
                title_lookup[title_key] = key

        else:

            existing = unique_papers[existing_key]

            sources = set(existing.source.split(" + "))
            sources.add(paper.source)

            updates = {
                "source": " + ".join(sorted(sources))
            }

            if not existing.abstract and paper.abstract:
                updates["abstract"] = paper.abstract

            if not existing.doi and paper.doi:
                updates["doi"] = paper.doi

            if not existing.authors and paper.authors:
                updates["authors"] = paper.authors

            if not existing.paper_url and paper.paper_url:
                updates["paper_url"] = paper.paper_url

            unique_papers[existing_key] = existing.model_copy(
                update=updates
            )

    return list(unique_papers.values())


def discover_papers(
    tasks: list[ResearchTask]
) -> list[PaperSearchResult]:

    discovery_results = []

    for task_index, task in enumerate(tasks):

        collected_papers = []

        keywords_to_search = task.search_keywords[:2]

        for keyword_index, keyword in enumerate(keywords_to_search):

            # OpenAlex search
            openalex_papers = search_openalex(
                keyword=keyword,
                limit=3
            )

            collected_papers.extend(openalex_papers)

            # arXiv search
            # Respect spacing between successive arXiv requests.
            if keyword_index > 0 or task_index > 0:
                time.sleep(3)

            arxiv_papers = search_arxiv(
                keyword=keyword,
                limit=3
            )

            collected_papers.extend(arxiv_papers)

        unique_papers = merge_papers(collected_papers)

        discovery_results.append(
            PaperSearchResult(
                task_id=task.task_id,
                task_title=task.title,
                papers=unique_papers,
                total_found=len(unique_papers)
            )
        )

    return discovery_results