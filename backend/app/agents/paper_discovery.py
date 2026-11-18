from app.schemas.research import ResearchTask
from app.schemas.paper import PaperSearchResult
from app.services.openalex_service import search_openalex


def discover_papers(tasks: list[ResearchTask]) -> list[PaperSearchResult]:

    discovery_results = []

    for task in tasks:

        collected_papers = []
        seen_paper_ids = set()

        # Use at most two keywords per task initially.
        keywords_to_search = task.search_keywords[:2]

        for keyword in keywords_to_search:

            papers = search_openalex(keyword, limit=3)

            for paper in papers:

                if paper.paper_id not in seen_paper_ids:
                    seen_paper_ids.add(paper.paper_id)
                    collected_papers.append(paper)

        result = PaperSearchResult(
            task_id=task.task_id,
            task_title=task.title,
            papers=collected_papers,
            total_found=len(collected_papers)
        )

        discovery_results.append(result)

    return discovery_results