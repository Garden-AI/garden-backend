import json
import pytest

from lambda_function import lambda_handler
from tiny_router import RouteNotFoundException


def test_sanity() -> None:
    events = [
        {"path": "/hello-world", "httpMethod": "GET"},
        {"path": "/route/we/do/not/support", "httpMethod": "GET"},
    ]

    assert json.loads(lambda_handler(events[0], None)["body"])["success"]
    with pytest.raises(RouteNotFoundException):
        lambda_handler(events[1], None)


def test_doi(mocker) -> None:
    class DummyReply:
        def __init__(self) -> None:
            self.status_code = 200
        def json(self) -> dict:
            return {"data": {"attributes": {"doi": "10.23677/fake-doi"}}}
        def raise_for_status(self) -> None:
            pass

    mocker.patch("requests.post", return_value=DummyReply())
    mocker.patch("requests.put", return_value=DummyReply())
    events = [
        {"path": "/doi", "httpMethod": "POST", "body": json.dumps({"data": {"type": "dois", "attributes": {}}})},
        {"path": "/doi", "httpMethod": "PUT", "body": json.dumps({"data": {"type": "dois", "attributes": {"identifiers": [
                                                                                                         {"identifier": "10.23677/fake-doi"}]}}})},
    ]

    assert (res:=lambda_handler(events[0], None))["statusCode"] == 201 and "10." in json.loads(res["body"])["doi"]
    assert (res:=lambda_handler(events[1], None))["statusCode"] == 200 and not json.loads(res["body"])



def test_presigned_url() -> None:
    payloads = [
        json.dumps({"direction": "not-a-direction", "batch": ["willengler@uchicago.edu/example-model/model.zip"]}),
        json.dumps({"direction": "upload", "batch": ["willengler@uchicago.edu/example-model/model.tar"]}),
        json.dumps({"direction": "upload", "batch": ["willengler@uchicago.edu/example-model/model.zip"]}),
        json.dumps({"direction": "download", "batch": ["willengler@uchicago.edu/example-model/model.zip",
                                                       "willengler@uchicago.edu/sample-model/model.zip"]}),
    ]
    events = [{"path": "/presigned-url", "httpMethod": "POST", "body": payload} for payload in payloads]

    assert (res:=lambda_handler(events[0], None))["statusCode"] == 400 and "direction" in json.loads(res["body"])["message"]
    assert (res:=lambda_handler(events[1], None))["statusCode"] == 400 and "format" in json.loads(res["body"])["responses"][0]["body"]["message"]
    assert (res:=lambda_handler(events[2], None))["statusCode"] == 200 and json.loads(res["body"])  # make sure return body is valid json
    assert (res:=lambda_handler(events[3], None))["statusCode"] == 200 and json.loads(res["body"])


def test_garden_search_record(mocker) -> None:
    mocker.patch("globus_sdk.SearchClient.create_entry", return_value={"task_id": None})
    event = {"path": "/garden-search-record", "httpMethod": "POST", "body": json.dumps({"doi": "10.23677/fake-doi"})}
    mocker.patch("globus_sdk.SearchClient.get_task", return_value={"state": "PENDING", "task_id": "uuid-here", "fatal_error": "Globus error"})
    assert lambda_handler(event, None)["statusCode"] == 408
    mocker.patch("globus_sdk.SearchClient.get_task", return_value={"state": "FAILED", "task_id": "uuid-here", "fatal_error": "Globus error"})
    assert lambda_handler(event, None)["statusCode"] == 500
    mocker.patch("globus_sdk.SearchClient.get_task", return_value={"state": "SUCCESS", "task_id": "uuid-here", "fatal_error": "Globus error"})
    assert lambda_handler(event, None)["statusCode"] == 200
