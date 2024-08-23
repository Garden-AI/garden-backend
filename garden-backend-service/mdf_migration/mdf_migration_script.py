import asyncio

import boto3
import httpx
import requests
import rich
from boto3.dynamodb.conditions import Attr
from src.api.schemas.search.globus_search import GSearchResult
from src.auth.globus_auth import get_mdf_auth_client
from src.config import get_settings


async def migrate_all_records():
    """
    Pulls down all records from the search index.
    For each record, get versioned_source_id from the recods subject and try to parse DOI
        - Some old records do not have a DOI associated with them.
    For each record, look up versioned_source_id in the dynamo table `MDF_STATUS_TABLE_NAME`
        - Some old records do not have a status record in any of the dynamodb tables
            - This is not great since its the only place we can get the owners globus ids from
            - Checking every record on the search index, I was able to get user ids for 378 records and unable to for 425 records
            - As far as i can tell, the status table is the only place we could get the owner id for records in the search index.
              So I think if we want to still keep track of those records we will need to make owner nullable for datasets.

    For records that the script was able to find a owner id for, send put request to `/mdf/put`
    that creates the user record if needed and creates the dataset record. `/mdf/put` requires MDF cc auth.

    Returns which records succeeded and which records failed.
    """

    MDF_SEARCH_INDEX_UUID = "1a57bbe5-5272-477f-9d31-343b8258b7a5"
    MDF_STATUS_TABLE_NAME = "prod-status-alpha-1"
    API_URL = "http://localhost:5500/mdf/put"

    settings = get_settings()
    mdf_auth_client = get_mdf_auth_client()

    dynamo_table = _get_dynamo_table(
        settings.AWS_ACCESS_KEY_ID,
        settings.AWS_SECRET_ACCESS_KEY,
        MDF_STATUS_TABLE_NAME,
    )

    token_response = mdf_auth_client.oauth2_client_credentials_tokens()
    access_token = token_response.by_resource_server["auth.globus.org"]["access_token"]
    authorization_header = f"Bearer {access_token}"
    auth_header = {"Authorization": authorization_header}

    records = await _get_all_records(MDF_SEARCH_INDEX_UUID)

    succeeded = []
    failed = []

    for record_key, record_data in records.items():
        print(f"Starting migration for: {record_key}")
        try:
            await migrate_mdf_record(
                settings,
                dynamo_table,
                API_URL,
                auth_header,
                record_key,
                record_data["doi"],
            )
            succeeded.append(record_key)
        except Exception as e:
            failed.append({record_key: str(e)})

    return {"succeeded": succeeded, "failed": failed}


async def migrate_mdf_record(
    settings, dynamo_table, api_url, auth_header, versioned_source_id, doi
):
    dynamo_record = _scan_dynamo_table(
        dynamo_table, filters=[("source_id", "==", versioned_source_id)]
    )

    dynamo_result = dynamo_record.get("results", [])
    if len(dynamo_result) != 1:
        raise Exception("Failed to find record in dynamo table")
    user_identity_uuid = dynamo_result[0].get("user_id", None)
    if user_identity_uuid is None:
        raise Exception("Failed to find owner identity_uuid in dynamo table")

    response = requests.put(
        api_url,
        headers=auth_header,
        json={
            "versioned_source_id": versioned_source_id,
            "doi": doi,
            "user_identity_uuid": user_identity_uuid,
        },
    )

    if response.status_code != 200:
        raise Exception(f"Server failed to create record: {response.json()}")


async def _get_all_records(search_index_uuid):
    query = {
        "q": "*",
        "limit": 1000,
        "advanced": True,
        "filters": [
            {
                "type": "match_all",
                "field_name": "mdf.resource_type",
                "values": ["dataset"],
            }
        ],
    }

    async with httpx.AsyncClient() as client:
        query_results = await client.post(
            f"https://search.api.globus.org/v1/index/{search_index_uuid}/search",
            json=query,
            headers={"Content-Type": "application/json"},
        )

    gsearch_result = GSearchResult(**query_results.json())

    records = {}

    for record in gsearch_result.gmeta:
        versioned_source_id = record.root.subject
        try:
            identifier = (
                record.root.entries[0]
                .get("content", {})
                .get("dc", {})
                .get("identifier", {})
            )

            identifier_type = identifier.get("identifierType", None)
            doi = identifier.get("identifier", None)
            if identifier_type != "DOI":
                doi = None
        except Exception:
            doi = None

        records[versioned_source_id] = {"doi": doi}

    return records


def _get_dynamo_table(aws_access_key_id, aws_secret_access_key, table_name):
    dynamodb = boto3.resource(
        "dynamodb",
        region_name="us-east-1",
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
    )

    table = dynamodb.Table(table_name)
    return table


def _scan_dynamo_table(table, fields=None, filters=None):
    """Scan the status or curation databases..

    Arguments:
    table_name (str): The Dynamo table to scan.
    fields (list of str): The fields from the results to return.
                          Default None, to return all fields.
    filters (list of tuples): The filters to apply. Format: (field, operator, value)
                              For an entry to be returned, all filters must match.
                              Default None, to return all entries.
                           field: The status field to filter on.
                           operator: The relation of field to value. Valid operators:
                                     ^: Begins with
                                     *: Contains
                                     ==: Equal to (or field does not exist, if value is None)
                                     !=: Not equal to (or field exists, if value is None)
                                     >: Greater than
                                     >=: Greater than or equal to
                                     <: Less than
                                     <=: Less than or equal to
                                     []: Between, inclusive (requires a list of two values)
                                     in: Is one of the values (requires a list of values)
                                         This operator effectively allows OR-ing '=='
                           value: The value of the field.

    Returns:
    dict: The results of the scan.
        success (bool): True on success, False otherwise.
        results (list of dict): The status entries returned.
        error (str): If success is False, the error that occurred.
    """

    # Translate fields
    if isinstance(fields, str) or fields is None:
        proj_exp = fields
    elif isinstance(fields, list):
        proj_exp = ",".join(fields)
    else:
        return {
            "success": False,
            "error": "Invalid fields type {}: '{}'".format(type(fields), fields),
        }

    # Translate filters
    # 0 = field
    # 1 = operator
    # 2 = value
    if isinstance(filters, tuple):
        filters = [filters]
    if filters is None or (isinstance(filters, list) and len(filters) == 0):
        filter_exps = None
    elif isinstance(filters, list):
        filter_exps = []
        for fil in filters:
            # Begins with
            if fil[1] == "^":
                filter_exps.append(Attr(fil[0]).begins_with(fil[2]))
            # Contains
            elif fil[1] == "*":
                filter_exps.append(Attr(fil[0]).contains(fil[2]))
            # Equal to (or field does not exist, if value is None)
            elif fil[1] == "==":
                if fil[2] is None:
                    filter_exps.append(Attr(fil[0]).not_exists())
                else:
                    filter_exps.append(Attr(fil[0]).eq(fil[2]))
            # Not equal to (or field exists, if value is None)
            elif fil[1] == "!=":
                if fil[2] is None:
                    filter_exps.append(Attr(fil[0]).exists())
                else:
                    filter_exps.append(Attr(fil[0]).ne(fil[2]))
            # Greater than
            elif fil[1] == ">":
                filter_exps.append(Attr(fil[0]).gt(fil[2]))
            # Greater than or equal to
            elif fil[1] == ">=":
                filter_exps.append(Attr(fil[0]).gte(fil[2]))
            # Less than
            elif fil[1] == "<":
                filter_exps.append(Attr(fil[0]).lt(fil[2]))
            # Less than or equal to
            elif fil[1] == "<=":
                filter_exps.append(Attr(fil[0]).lte(fil[2]))
            # Between, inclusive (requires a list of two values)
            elif fil[1] == "[]":
                if not isinstance(fil[2], list) or len(fil[2]) != 2:
                    return {
                        "success": False,
                        "error": "Invalid between ('[]') operator values: '{}'".format(
                            fil[2]
                        ),
                    }
                filter_exps.append(Attr(fil[0]).between(fil[2][0], fil[2][1]))
            # Is one of the values (requires a list of values)
            elif fil[1] == "in":
                if not isinstance(fil[2], list):
                    return {
                        "success": False,
                        "error": "Invalid 'in' operator values: '{}'".format(fil[2]),
                    }
                filter_exps.append(Attr(fil[0]).is_in(fil[2]))
            else:
                return {
                    "success": False,
                    "error": "Invalid filter operator '{}'".format(fil[1]),
                }
    else:
        return {
            "success": False,
            "error": "Invalid filters type {}: '{}'".format(type(filters), filters),
        }

    # Make scan arguments
    scan_args = {"ConsistentRead": True}
    if proj_exp is not None:
        scan_args["ProjectionExpression"] = proj_exp
    if filter_exps is not None:
        # Create valid FilterExpression
        # Each Attr must be combined with &
        filter_expression = filter_exps[0]
        for i in range(1, len(filter_exps)):
            filter_expression = filter_expression & filter_exps[i]
        scan_args["FilterExpression"] = filter_expression

    # Make scan call, paging through if too many entries are scanned
    result_entries = []
    while True:
        scan_res = table.scan(**scan_args)
        # Check for success
        if scan_res["ResponseMetadata"]["HTTPStatusCode"] >= 300:
            return {
                "success": False,
                "error": (
                    "HTTP code {} returned: {}".format(
                        scan_res["ResponseMetadata"]["HTTPStatusCode"],
                        scan_res["ResponseMetadata"],
                    )
                ),
            }
        # Add results to list
        result_entries.extend(scan_res["Items"])
        # Check for completeness
        # If LastEvaluatedKey exists, need to page through more results
        if scan_res.get("LastEvaluatedKey", None) is not None:
            scan_args["ExclusiveStartKey"] = scan_res["LastEvaluatedKey"]
        # Otherwise, all results retrieved
        else:
            break

    return {"success": True, "results": result_entries}


def _get_dynamo_record(dynamo_table, versioned_source_id):
    dynamo_record = _scan_dynamo_table(
        dynamo_table, filters=[("source_id", "==", versioned_source_id)]
    )
    return dynamo_record


async def _get_single_record(versioned_source_id, search_index_uuid):
    query = {
        "q": f"{versioned_source_id}",
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

    async with httpx.AsyncClient() as client:
        query_results = await client.post(
            f"https://search.api.globus.org/v1/index/{search_index_uuid}/search",
            json=query,
            headers={"Content-Type": "application/json"},
        )
        return query_results.json()


result = asyncio.run(migrate_all_records())
num_succeeded = len(result["succeeded"])
num_failed = len(result["failed"])
rich.print_json(data=result)
print(f"num succeeded: {num_succeeded}, num failed {num_failed}")
