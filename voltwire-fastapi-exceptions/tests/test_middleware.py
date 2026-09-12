import asyncio
import json

from fastapi.exceptions import RequestValidationError
from starlette import status
from starlette.requests import Request

from voltwire.fastapi.exceptions import (
    DefaultExceptionHandlerSettings,
    EntityNotFoundError,
    build_error_responses,
    build_validation_handler,
)
from voltwire.fastapi.exceptions.middleware import _handle_service_error, _handle_unexpected_error


class FakeApiMessage:
    def __init__(self, *, message: str, errors: list[str]):
        self.message = message
        self.errors = errors

    def model_dump(self, *, mode: str = "json", exclude_none: bool = True) -> dict:
        return {"message": self.message, "errors": self.errors}


def _request(path: str = "/x") -> Request:
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "server": ("test", 80),
            "path": path,
            "query_string": b"",
            "headers": [],
        }
    )


def _body(response) -> dict:
    return json.loads(response.body)


def test_service_error_uses_caller_model():
    response = _handle_service_error(_request(), EntityNotFoundError("nope"), FakeApiMessage)
    assert response.status_code == 404
    assert _body(response) == {"message": "service error", "errors": ["nope"]}


def test_unexpected_error_hides_detail_in_production():
    response = _handle_unexpected_error(
        _request(), ValueError("boom"), DefaultExceptionHandlerSettings(production=True), FakeApiMessage
    )
    assert response.status_code == 500
    assert _body(response)["errors"] == []


def test_unexpected_error_includes_detail_outside_production():
    response = _handle_unexpected_error(
        _request(), ValueError("boom"), DefaultExceptionHandlerSettings(production=False), FakeApiMessage
    )
    assert response.status_code == 500
    assert _body(response)["errors"] == ["boom"]


def test_validation_handler_uses_caller_model():
    handler = build_validation_handler(FakeApiMessage)
    exc = RequestValidationError([{"loc": ("body", "name"), "msg": "field required", "type": "missing", "input": None}])
    response = asyncio.run(handler(_request(), exc))
    assert response.status_code == 422
    body = _body(response)
    assert body["message"] == "Request Validation Error"
    assert len(body["errors"]) == 1
    assert "field required" in body["errors"][0]


def test_build_error_responses_maps_caller_model():
    responses = build_error_responses(FakeApiMessage)
    for code in (
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_409_CONFLICT,
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        status.HTTP_400_BAD_REQUEST,
    ):
        assert responses[code]["model"] is FakeApiMessage
        assert responses[code]["description"]
