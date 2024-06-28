import requests
from fastapi import APIRouter, Body, Depends, exceptions, status
from src.api.dependencies.auth import AuthenticationState, authenticated
from src.api.schemas import datacite
from src.config import Settings, get_settings

router = APIRouter(prefix="/doi")


@router.post("", status_code=status.HTTP_201_CREATED)
async def mint_draft_doi(
    body: datacite.Doi = Body(
        examples=[
            {
                "data": {"type": "dois", "attributes": {}},
            }
        ]
    ),
    settings: Settings = Depends(get_settings),
    _auth: AuthenticationState = Depends(authenticated),
):
    body.data.attributes.prefix = settings.DATACITE_PREFIX
    try:
        resp: requests.Response = requests.post(
            settings.DATACITE_ENDPOINT,
            headers={"Content-Type": "application/vnd.api+json"},
            json=body.model_dump(exclude_unset=True),
            auth=(settings.DATACITE_REPO_ID, settings.DATACITE_PASSWORD),
        )
        resp.raise_for_status()
    except requests.HTTPError as e:
        raise exceptions.HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )

    # note: datacite response body uses same schema
    result = datacite.Doi(**resp.json())
    return {"doi": result.data.attributes.doi}


@router.put("", status_code=status.HTTP_200_OK)
async def update_datacite(
    body: datacite.Doi = Body(
        examples=[
            {
                "data": {
                    "type": "dois",
                    "attributes": {
                        "types": {
                            "resourceType": "AI/ML Garden",
                            "resourceTypeGeneral": "Software",
                        },
                        "identifiers": [
                            {
                                "identifier": "10.23677/fakedoi-1234",
                                "identifierType": "DOI",
                            }
                        ],
                        "creators": [
                            {
                                "name": "Mendel, Gregor",
                            }
                        ],
                        "titles": [
                            {
                                "title": "GPT Garden (Generative Pea-trained Transformers)",
                            }
                        ],
                        "publisher": "thegardens.ai",
                        "publicationYear": "2024",
                        "contributors": [],
                        # "event": "publish",
                        # "url": "https://thegardens.ai/10.23677/fakedoi-1234",
                    },
                }
            }
        ]
    ),
    settings: Settings = Depends(get_settings),
    _auth: AuthenticationState = Depends(authenticated),
):
    body.data.attributes.prefix = settings.DATACITE_PREFIX
    try:
        doi = body.data.attributes.identifiers[0].identifier
        resp: requests.Response = requests.put(
            f"{settings.DATACITE_ENDPOINT}/{doi}",
            headers={"Content-Type": "application/vnd.api+json"},
            json=body.model_dump(exclude_unset=True),
            auth=(settings.DATACITE_REPO_ID, settings.DATACITE_PASSWORD),
        )
        resp.raise_for_status()
    except requests.HTTPError as e:
        raise exceptions.HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )

    result = datacite.Doi(**resp.json())
    return result.model_dump(exclude_defaults=True)
