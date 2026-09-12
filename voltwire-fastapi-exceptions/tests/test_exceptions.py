from starlette import status

from voltwire.fastapi.exceptions import (
    BadRequestError,
    DownstreamServiceError,
    EntityNotFoundError,
    ForbiddenError,
    ResourceConflictError,
    AppError,
    AppWarning,
    UnauthorizedRequestError,
    UnprocessableRequestError,
    UnsupportedFeatureError,
)


def test_subclass_status_codes_and_default_messages():
    cases = [
        (UnauthorizedRequestError(), status.HTTP_401_UNAUTHORIZED),
        (ForbiddenError(), status.HTTP_403_FORBIDDEN),
        (BadRequestError(), status.HTTP_400_BAD_REQUEST),
        (EntityNotFoundError(), status.HTTP_404_NOT_FOUND),
        (ResourceConflictError(), status.HTTP_409_CONFLICT),
        (UnprocessableRequestError(), status.HTTP_422_UNPROCESSABLE_ENTITY),
        (UnsupportedFeatureError(), status.HTTP_501_NOT_IMPLEMENTED),
        (DownstreamServiceError(), status.HTTP_502_BAD_GATEWAY),
    ]
    for err, code in cases:
        assert err.status_code == code
        assert isinstance(err.message, str) and err.message


def test_custom_message_and_str():
    err = EntityNotFoundError("no user 5")
    assert err.message == "no user 5"
    assert str(err) == "no user 5"


def test_warnings_are_service_errors():
    assert issubclass(AppWarning, AppError)
    assert isinstance(ForbiddenError(), AppWarning)
    assert isinstance(UnsupportedFeatureError(), AppWarning)
    assert not isinstance(BadRequestError(), AppWarning)
