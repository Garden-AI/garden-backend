import asyncio
import logging
from datetime import datetime

import globus_sdk
import httpx
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from src.api.dependencies.search import query_mdf_search
from src.api.schemas.search.globus_search import GSearchResult
from src.auth.globus_groups import add_identity_id_to_group
from src.config import Settings
from src.models import Dataset, PendingMDFFlow, User

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())


async def check_active_mdf_flows(
    settings: Settings,
    db_session: async_sessionmaker,
    garden_auth_client: globus_sdk.ConfidentialAppAuthClient,
    flows_client: globus_sdk.FlowsClient,
):
    """
    Grabs all pending flows stored in `pending-mdf-flows` table and checks if the flow has completed.
    If the flow has completed, delete the pending record and create new dataset record in `mdf-datasets` table.
    If the flow has not completed, increament retry_count and update last attempt time.
    """

    while settings.MDF_POLL_FLOWS:
        try:
            async with db_session() as db:
                active_flows = await _get_active_flows(db, settings)
                await _process_active_flows(
                    active_flows, db, settings, garden_auth_client, flows_client
                )
        except asyncio.CancelledError:
            logger.info("Synchronization loop canceled.")
            break
        except Exception as e:
            logger.error(f"Error in synchronization loop: {e}")

        await asyncio.sleep(settings.MDF_RETRY_INTERVAL_SECS)


async def _get_active_flows(
    db: AsyncSession,
    settings: Settings,
) -> list[PendingMDFFlow]:
    """Grabs all pending MDF flows that have a retry_count less than MDF_MAX_RETRY_COUNT"""
    result = await db.scalars(
        select(PendingMDFFlow)
        .where(PendingMDFFlow.retry_count < settings.MDF_MAX_RETRY_COUNT)
        .order_by(PendingMDFFlow.last_attempt)
    )
    return result.all()


async def _process_active_flows(
    active_flows: list[PendingMDFFlow],
    db: AsyncSession,
    settings: Settings,
    garden_auth_client: globus_sdk.ConfidentialAppAuthClient,
    flows_client: globus_sdk.FlowsClient,
):
    """
    For each flow in active_flows, check if its run info has the completion_time field.
    If it does, the flow has completed, so create new dataset in `mdf-datasets` table.
    If not or if it fails to create the new dataset, increment retry_count and update last attempt.
    """
    for flow in active_flows:
        failed = True
        try:
            flow_info = flows_client.get_run(flow.flow_action_id)
            if flow_info.status_code == 200:
                is_completed = flow_info.get("completion_time", None) is not None
                if is_completed:
                    try:
                        await _add_dataset_from_completed_flow(
                            flow, db, settings, garden_auth_client
                        )
                        failed = False
                    except Exception as error:
                        logger.error(
                            f"Error adding completed flow {flow.flow_action_id}: {str(error)}"
                        )
            else:
                logger.error(
                    f"Unable to get run info from globus for flow {flow.versioned_source_id}, returned status code: {flow_info.status_code}"
                )
        except globus_sdk.FlowsAPIError as globus_error:
            logger.error(
                f"Unable to get run info from globus for flow {flow.versioned_source_id}, globus returned error: {str(globus_error)}"
            )

        if failed:
            flow.retry_count += 1
            flow.last_attempt = datetime.now()
            try:
                await db.commit()
            except IntegrityError:
                logger.error(
                    f"Unable to increment retry_count for pending mdf flow {flow.versioned_source_id}"
                )
                await db.rollback()


async def _add_dataset_from_completed_flow(
    flow: PendingMDFFlow,
    db: AsyncSession,
    settings: Settings,
    garden_auth_client: globus_sdk.ConfidentialAppAuthClient,
):
    """
    Checks to see if any of the flows in active_flows have the completion_time field.
    If it does, add the dataset to our table, if not, increment retry_count
    """
    query = {
        "q": f"{flow.versioned_source_id}",
        "limit": 1,
        "advanced": True,
        "filters": [
            {
                "type": "match_all",
                "field_name": "mdf.resource_type",
                "values": ["dataset"],
            }
        ],
    }

    query_response = await query_mdf_search(query, settings)
    doi = _parse_doi(query_response)
    mdf_user = await _get_or_create_user(
        flow.owner_identity_id, db, settings, garden_auth_client
    )

    new_dataset = Dataset(
        versioned_source_id=flow.versioned_source_id,
        doi=doi,
        owner=mdf_user,
        previous_versions=flow.previous_versions,
    )

    await db.delete(flow)
    db.add(new_dataset)
    try:
        await db.commit()
        logger.info(
            f"Added new dataset {flow.versioned_source_id} to mdf-datasets table"
        )
    except IntegrityError as e:
        logger.error(
            f"Unable to add new dataset {flow.versioned_source_id} to mdf_datasets table"
        )
        await db.rollback()
        raise e


async def _get_or_create_user(
    user_identity_uuid: str,
    db: AsyncSession,
    settings: Settings,
    garden_auth_client: globus_sdk.ConfidentialAppAuthClient,
) -> User:
    """
    Checks if globus user identity_uuid is already in the `users` table.
    If so, return existing user record.
    If not, create new user record and add to garden group.
    """
    user, created = await User.get_or_create(
        db,
        identity_id=user_identity_uuid,
    )

    if created:
        user_identities = garden_auth_client.get_identities(ids=user_identity_uuid)
        user_info = user_identities.get("identities", [{}])[0]
        user.name = user_info.get("name", None)
        user.email = user_info.get("email", None)
        user.username = user_info.get("username", None)

        try:
            await db.commit()
        except IntegrityError as e:
            logger.error(
                msg=f"Unable to create new user for MDF user {user_identity_uuid}"
            )
            await db.rollback()
            raise e

        add_identity_id_to_group(user_identity_uuid, settings)

    return user


def _parse_doi(query_response: httpx.Response) -> str:
    """
    Tries to parse MDF dataset DOI from globus search result.
    If unable to parse DOI or search returns bad response, raise ValueError
    """
    if query_response.status_code == 200:
        gsearch_result = GSearchResult(**query_response.json())
        if gsearch_result.count == 0:
            raise ValueError(
                "Unable to parse DOI, search result for pending MDF dataset returned no results."
            )
        elif gsearch_result.count > 1:
            raise ValueError(
                "Unable to parse DOI, search result for pending MDF dataset returned multiple results."
            )
        else:
            identifier = (
                gsearch_result.gmeta[0]
                .root.entries[0]
                .get("content", {})
                .get("dc", {})
                .get("identifier", {})
            )

            identifier_type = identifier.get("identifierType", None)
            doi = identifier.get("identifier", None)

            if identifier_type == "DOI" and doi is not None:
                return doi
            else:
                raise ValueError(
                    "Unable to parse DOI, search result did not match expected format."
                )
    else:
        raise ValueError(
            f"Unable to parse DOI, search query returned non 200 status code {query_response.status_code}"
        )
