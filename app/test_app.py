import json
import pytest

from lambda_function import lambda_handler
from tiny_router import RouteNotFoundException

# Imitate the GlobusHTTPResponse
class DictWithText(dict):
    def __init__(self, initial_dict=None, text=""):
        super().__init__(initial_dict if initial_dict is not None else {})
        self.text = text

@pytest.fixture(autouse=True)
def mock_get_environment_from_arn(mocker):
    import os
    os.environ["AWS_LAMBDA_FUNCTION_NAME"] = "fake_lambda_name-dev"

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


def test_garden_search_record(mocker) -> None:
    mocker.patch("globus_sdk.SearchClient.create_entry", return_value={"task_id": None})
    event = {"path": "/garden-search-record", "httpMethod": "POST", "body": json.dumps({"doi": "10.23677/fake-doi"})}
    mocker.patch("globus_sdk.SearchClient.get_task", return_value={"state": "PENDING", "task_id": "uuid-here", "fatal_error": "Globus error"})
    assert lambda_handler(event, None)["statusCode"] == 408
    failure_response = DictWithText(initial_dict={"state": "FAILED", "task_id": "uuid-here", "fatal_error": "Globus error"}, text="Globus error")
    mocker.patch("globus_sdk.SearchClient.get_task", return_value=failure_response)
    assert lambda_handler(event, None)["statusCode"] == 500
    mocker.patch("globus_sdk.SearchClient.get_task", return_value={"state": "SUCCESS", "task_id": "uuid-here", "fatal_error": "Globus error"})
    assert lambda_handler(event, None)["statusCode"] == 200
