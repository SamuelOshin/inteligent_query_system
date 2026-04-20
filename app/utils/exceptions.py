"""
utils/exceptions.py

Custom exception classes that carry both a message and an HTTP status code.
Service layer raises these — main.py registers handlers that catch them
and call error_response(). Routes never see try/except blocks.

Rule:
  - Service raises the right exception type for the right condition
  - Handler in main.py maps exception type → error_response()
  - Routes are completely clean of error handling logic
"""


class AppBaseException(Exception):
    """
    Base for all application exceptions.
    Carries the message and the HTTP status code to respond with.
    """
    status_code: int = 500
    default_message: str = "An unexpected error occurred"

    def __init__(self, message: str | None = None):
        self.message = message or self.default_message
        super().__init__(self.message)


class BadRequestError(AppBaseException):
    """
    400 — Request is malformed or logically invalid.
    Examples: empty name, whitespace-only NL query.
    """
    status_code = 400
    default_message = "Bad request"


class NotFoundError(AppBaseException):
    """
    404 — Requested resource does not exist.
    Examples: profile ID not in database.
    """
    status_code = 404
    default_message = "Resource not found"


class UnprocessableError(AppBaseException):
    """
    422 — Request is structurally valid but semantically invalid.
    Examples: invalid gender value, min_age > max_age, invalid sort_by.
    """
    status_code = 422
    default_message = "Unprocessable entity"


class ExternalAPIError(AppBaseException):
    """
    502 — An upstream external API returned an invalid or null response.
    Examples: genderize returned null gender, agify returned null age.
    """
    status_code = 502
    default_message = "External API returned an invalid response"


class InternalError(AppBaseException):
    """
    500 — Unexpected server-side failure.
    """
    status_code = 500
    default_message = "Internal server error"
