import pytest

from src.api.schemas.papers import LinkArxivMetadataRequest


@pytest.mark.asyncio
async def test_extract_arxiv_identifier_abs_format():
    request = LinkArxivMetadataRequest(url="https://arxiv.org/abs/2301.04589")
    assert request.arxiv_identifier == "2301.04589"


@pytest.mark.asyncio
async def test_extract_arxiv_identifier_pdf_format():
    request = LinkArxivMetadataRequest(url="https://arxiv.org/pdf/2301.04589.pdf")
    assert request.arxiv_identifier == "2301.04589"
