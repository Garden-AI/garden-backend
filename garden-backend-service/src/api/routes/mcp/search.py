import json
from typing import Optional
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import array

from src.api.dependencies.database import get_db_session_maker, get_settings
from src.api.schemas.garden import GardenMetadataResponse
from src.models import Garden, ModalFunction, User
from src.models.modal.modal_function import ModalFunction
from src.api.routes.mcp.mcp_server import mcp

logger = structlog.get_logger()


@mcp.tool()
async def search_gardens(
    doi: Optional[list[str]] = None,
    draft: Optional[bool] = None,
    owner_uuid: Optional[UUID] = None,
    authors: Optional[list[str]] = None,
    contributors: Optional[list[str]] = None,
    tags: Optional[list[str]] = None,
    year: Optional[str] = None,
    function_ids: Optional[list[int]] = None,
    limit: int = 10,
) -> str:
    settings = get_settings()
    session_maker = await get_db_session_maker(settings)

    try:
        async with session_maker() as db:
            if function_ids is not None:
                stmt = select(Garden).where(
                    Garden.modal_functions.any(ModalFunction.id.in_(function_ids))
                )
                result = await db.scalars(stmt.limit(limit))
                gardens = result.all()

                # Convert to Pydantic models and serialize properly
                garden_responses = [
                    GardenMetadataResponse.model_validate(garden) for garden in gardens
                ]
                return json.dumps(
                    [garden.model_dump() for garden in garden_responses],
                    indent=2,
                    default=str,
                )

            # Handle general search
            stmt = select(Garden)

            if doi is not None:
                stmt = stmt.where(Garden.doi.in_(doi))

            if draft is not None:
                stmt = stmt.where(Garden.doi_is_draft == draft)

            if owner_uuid is not None:
                stmt = stmt.join(Garden.user).where(User.identity_id == owner_uuid)

            if authors is not None:
                stmt = stmt.where(Garden.authors.overlap(array(authors)))

            if contributors is not None:
                stmt = stmt.where(Garden.contributors.overlap(array(contributors)))

            if tags is not None:
                stmt = stmt.where(Garden.tags.overlap(array(tags)))

            if year is not None:
                stmt = stmt.where(Garden.year == year)

            result = await db.scalars(stmt.limit(limit))
            gardens = result.all()

            # Convert to Pydantic models and serialize properly
            garden_responses = [
                GardenMetadataResponse.model_validate(garden) for garden in gardens
            ]
            return json.dumps(
                [garden.model_dump() for garden in garden_responses],
                indent=2,
                default=str,
            )

    except Exception as e:
        logger.error(e)
        return f"Error: {str(e)}"
