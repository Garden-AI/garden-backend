from typing import Annotated

from pydantic import AfterValidator, computed_field

from .base import BaseSchema, Url
from .shared_function_schemas import _PaperMetadata


def _is_arxiv_url(url: Url) -> Url:
    assert "arxiv.org" in str(url).lower(), "must be an arxiv url"
    return url


ArxivUrl = Annotated[Url, AfterValidator(_is_arxiv_url)]


class LinkArxivMetadataRequest(BaseSchema):
    url: ArxivUrl

    @computed_field
    @property
    def arxiv_identifier(self) -> str:
        url = str(self.url).strip()
        if "/pdf/" in url:
            # if the link looks like http://arxiv.org/pdf/{identifier}.pdf
            suffix = url.split("/pdf/")[-1]
            return suffix.split(".pdf")[0]
        elif "/abs/" in url:
            # otherwise url links to regular abstract page, not pdf
            return url.split("/abs/")[-1]
        else:
            raise ValueError(f"Failed to parse arXiv identifier from url {url}")


class LinkArxivMetadataResponse(_PaperMetadata):
    # makes url mandatory for arxiv papers
    url: ArxivUrl  # type: ignore
