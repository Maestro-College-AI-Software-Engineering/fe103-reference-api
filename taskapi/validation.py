"""Small input checks. Each check_* function returns (clean_value, error_message).

error_message is None when the value is fine; otherwise it becomes one entry in
the "fields" object of a 400 validation_error, for example {"title": "is required"}.
"""
import re
from datetime import date

from flask import request

from .errors import APIError, ValidationError

DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def get_json_object():
    """The request body as a dict, or a 400 if it is missing or not a JSON object."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise APIError(
            400, "invalid_json",
            "Send a JSON object in the body with the header 'Content-Type: application/json'.",
        )
    return data


def _text(value, minimum, maximum, required=True):
    if value is None:
        return None, ("is required" if required else None)
    if not isinstance(value, str):
        return None, "must be a string"
    value = value.strip()
    if not value:
        return None, ("cannot be blank" if required else None)
    if not minimum <= len(value) <= maximum:
        if minimum > 1:
            return None, f"must be between {minimum} and {maximum} characters"
        return None, f"must be at most {maximum} characters"
    return value, None


# Users -----------------------------------------------------------------------

def check_username(value):
    return _text(value, 3, 30)


def check_password(value):
    # Passwords are never trimmed: spaces count.
    if value is None or value == "":
        return None, "is required"
    if not isinstance(value, str):
        return None, "must be a string"
    if len(value) < 8:
        return None, "must be at least 8 characters"
    if len(value) > 128:
        return None, "must be at most 128 characters"
    return value, None


def check_display_name(value):
    # null clears the display name; a blank string is a mistake, not a clear.
    if value is None:
        return None, None
    value, error = _text(value, 1, 60)
    if error == "cannot be blank":
        error = "cannot be blank (send null to clear it)"
    return value, error


# Tasks -----------------------------------------------------------------------

def check_title(value):
    return _text(value, 1, 120)


def check_description(value):
    # Optional: null or "" (for example an empty textarea) is stored as null.
    return _text(value, 0, 1000, required=False)


def check_done(value):
    if not isinstance(value, bool):
        return None, "must be true or false"
    return value, None


def check_due_date(value):
    # Optional: null or "" (for example an empty <input type="date">) clears it.
    if value is None or value == "":
        return None, None
    if not isinstance(value, str) or not DATE_PATTERN.match(value):
        return None, "must be a date in YYYY-MM-DD format, or null"
    try:
        return date.fromisoformat(value), None
    except ValueError:
        return None, "must be a real calendar date in YYYY-MM-DD format"


TASK_FIELDS = {
    "title": check_title,
    "description": check_description,
    "done": check_done,
    "due_date": check_due_date,
}


def validate_task(data, partial):
    """Check a task body. partial=False for POST (title required), True for PATCH.

    Returns a dict of clean values for the fields that were sent. Keys that are
    not task fields (such as "id" or "owner_id") are ignored.
    """
    values, errors = {}, {}
    for name, check in TASK_FIELDS.items():
        if name not in data:
            if name == "title" and not partial:
                errors[name] = "is required"
            continue
        value, error = check(data[name])
        if error:
            errors[name] = error
        else:
            values[name] = value
    if errors:
        raise ValidationError(errors)
    if partial and not values:
        raise APIError(
            400, "validation_error",
            "Send at least one of: " + ", ".join(TASK_FIELDS) + ".",
        )
    return values


# Query strings ---------------------------------------------------------------

def query_int(name, default, maximum=None):
    """Read ?name=<whole number> from the URL. Returns (value, error_message)."""
    raw = request.args.get(name)
    if raw is None:
        return default, None
    if maximum:
        rule = f"must be a whole number from 1 to {maximum}"
    else:
        rule = "must be a whole number of 1 or more"
    raw = raw.strip()
    if not (raw.isascii() and raw.isdigit()):
        return None, rule
    try:
        value = int(raw)
    except ValueError:  # absurdly long numbers
        return None, rule
    if value < 1 or (maximum and value > maximum):
        return None, rule
    return value, None
