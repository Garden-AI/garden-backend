from urllib.parse import quote

import httpx
from fastapi import exceptions, status
from structlog import get_logger

from src.api.schemas import datacite
from src.config import Settings
from src.models.garden import Garden

logger = get_logger(__name__)


async def mint_draft_doi(settings: Settings) -> str:
    """
    Creates a new draft DOI with minimal attributes.

    Args:
        settings: Application settings containing DataCite credentials

    Returns:
        str: The newly minted DOI
    """
    data = {
        "data": {"type": "dois", "attributes": {"prefix": settings.DATACITE_PREFIX}}
    }
    body = datacite.Doi(**data)

    async with httpx.AsyncClient() as client:
        response: httpx.Response = await client.post(
            settings.DATACITE_ENDPOINT,
            headers={"Content-Type": "application/vnd.api+json"},
            auth=(settings.DATACITE_REPO_ID, settings.DATACITE_PASSWORD),
            json=body.model_dump(exclude_unset=True),
        )
        logger.info("Requested new draft DOI from datacite")
        try:
            response.raise_for_status()
        except httpx.HTTPError as e:
            raise exceptions.HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
            )
        # datacite response body uses same schema as request body
        result = datacite.Doi(**response.json())
        doi = result.data.attributes.doi
        logger.info("Minted draft DOI", doi=doi)
        return doi


async def update_doi_metadata(garden: Garden, settings: Settings):
    """
    Update the metadata for a garden on datacite without changing the state of the DOI.
    """
    await _make_request_to_datacite(garden, settings)


async def publish_doi(garden: Garden, settings: Settings):
    """
    Update the metadata for a garden on datacite, setting the DOI state to published.
    """
    await _make_request_to_datacite(garden, settings, event="publish")


async def archive_doi(garden: Garden, settings: Settings):
    """
    Update the metadata for a garden on datacite, setting the DOI state to archived.
    Note that archiving only applies to published DOIs, not draft DOIs.
    """
    await _make_request_to_datacite(garden, settings, event="hide")


async def _make_request_to_datacite(
    garden: Garden, settings: Settings, event: str | None = None
):
    body = _datacite_metadata_from_garden(garden)
    body.data.attributes.prefix = settings.DATACITE_PREFIX
    if event:
        body.data.attributes.event = event

    doi = garden.doi
    async with httpx.AsyncClient() as client:
        response = await client.put(
            f"{settings.DATACITE_ENDPOINT}/{doi}",
            headers={"Content-Type": "application/vnd.api+json"},
            auth=(settings.DATACITE_REPO_ID, settings.DATACITE_PASSWORD),
            json=body.model_dump(exclude_unset=True),
        )
        logger.info(f"Sent request to {event or 'update'} DOI on datacite", doi=doi)

    if response.status_code != 200:
        raise exceptions.HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update DOI {doi} on Datacite: {response.json()}",
        )


def _datacite_metadata_from_garden(garden: Garden) -> datacite.Doi:
    creators = [
        {"nameType": "Personal", "name": name}
        for name in set(garden.authors + garden.contributors)
    ]

    return datacite.Doi(
        data=datacite.DoiData(
            type="dois",
            attributes=datacite.DoiAttributes(
                types={
                    "resourceType": "AI Model Garden",
                    "resourceTypeGeneral": "Software",
                },
                identifiers=[
                    {
                        "identifier": garden.doi,
                        "identifierType": "DOI",
                    }
                ],
                creators=creators,
                titles=[
                    {
                        "title": garden.title,
                    }
                ],
                publisher="thegardens.ai",
                publicationYear=garden.year,
                url=f"https://thegardens.ai/#/garden/{quote(garden.doi, safe='')}",
            ),
        )
    )
