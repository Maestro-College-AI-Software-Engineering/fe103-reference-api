"""One error shape for every response that is not a success:

    {"error": {"code": "not_found", "message": "Task 42 does not exist."}}

Validation errors (400) add a "fields" object: {"title": "is required"}.
"""
from flask import jsonify, request
from werkzeug.exceptions import HTTPException

from .extensions import db


class APIError(Exception):
    """Raise this anywhere while handling a request to send an error response."""

    def __init__(self, status, code, message, fields=None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.fields = fields


class ValidationError(APIError):
    def __init__(self, fields, message="Some fields are invalid. See 'fields' for details."):
        super().__init__(400, "validation_error", message, fields)


def error_response(status, code, message, fields=None):
    body = {"code": code, "message": message}
    if fields:
        body["fields"] = fields
    response = jsonify(error=body)
    response.status_code = status
    return response


# Short messages for errors that Flask raises itself (no route, wrong method, ...).
HTTP_ERROR_MESSAGES = {
    400: "The request could not be understood.",
    401: "Log in first.",
    403: "You do not have access to this resource.",
    409: "The request conflicts with data that already exists.",
    500: "Something went wrong on the server. Try again later.",
}


def register_error_handlers(app):
    """Called from create_app, so no request ever gets an HTML error page."""

    @app.errorhandler(APIError)
    def handle_api_error(err):
        return error_response(err.status, err.code, err.message, err.fields)

    def handle_http_error(err):
        status = err.code or 500
        code = err.name.lower().replace(" ", "_")  # "Not Found" -> "not_found"
        if status == 404:
            message = f"No route matches {request.method} {request.path}."
        elif status == 405:
            allowed = ", ".join(sorted(err.valid_methods or []))
            message = f"{request.method} is not allowed on {request.path}. Allowed: {allowed}."
        else:
            message = HTTP_ERROR_MESSAGES.get(status, err.description)
        if status == 500:
            code = "internal_error"
            try:
                db.session.rollback()
            except Exception:  # the database itself may be the problem
                pass
        response = error_response(status, code, message)
        if status == 405 and err.valid_methods:
            response.headers["Allow"] = ", ".join(sorted(err.valid_methods))
        return response

    for status in (400, 401, 403, 404, 405, 409, 500):
        app.register_error_handler(status, handle_http_error)
    # Any other HTTP error (413 body too large, and so on) gets the same shape.
    app.register_error_handler(HTTPException, handle_http_error)
