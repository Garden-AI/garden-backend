import arxiv
from fastapi import APIRouter, HTTPException, status
from structlog import get_logger

from src.api.schemas.papers import LinkArxivMetadataRequest, LinkArxivMetadataResponse

logger = get_logger(__name__)
router = APIRouter(prefix="/arxiv-paper-metadata")


@router.post("")
def extract_arxiv_paper_metadata(
    request: LinkArxivMetadataRequest,
) -> LinkArxivMetadataResponse:
    # Use the arxiv package to fetch paper metadata
    try:
        client = arxiv.Client()
        search = arxiv.Search(id_list=[request.arxiv_identifier], max_results=1)
        results = list(client.results(search))
    except Exception as e:
        logger.exception(f"Error fetching arXiv metadata: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch arXiv metadata. Please try again later.",
        ) from e
    if not results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No arXiv paper found with identifier: {request.arxiv_identifier}",
        )
    paper = results[0]

    return LinkArxivMetadataResponse(
        title=paper.title,
        authors=[author.name for author in paper.authors],
        doi=paper.doi or None,
        url=request.url,
        description=paper.summary.replace("\n", " ").strip(),
        citation=paper.journal_ref or None,
    )
