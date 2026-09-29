"""Password hashing, JWT access tokens, and the @auth_required decorator."""
import hashlib
from datetime import datetime, timedelta, timezone
from functools import lru_cache, wraps

import jwt
from flask import current_app, g, request
from werkzeug.security import check_password_hash, generate_password_hash

from .errors import APIError
from .extensions import db
from .models import User

# Werkzeug's default method is scrypt. Apple's built-in Python 3.9 is compiled
# without scrypt, so fall back to PBKDF2 there. check_password_hash reads the
# method from the stored hash, so either kind verifies correctly.
PASSWORD_HASH_METHOD = "scrypt" if hasattr(hashlib, "scrypt") else "pbkdf2:sha256"


def hash_password(password):
    return generate_password_hash(password, method=PASSWORD_HASH_METHOD)


@lru_cache(maxsize=1)
def _dummy_hash():
    return hash_password("not-a-real-password")


def authenticate(username, password):
    """Return the user if the username and password match, otherwise None."""
    user = db.session.execute(
        db.select(User).filter_by(username=username)
    ).scalar_one_or_none()
    if user is None:
        # Do the same amount of work as a real check, so response times do not
        # reveal which usernames exist.
        check_password_hash(_dummy_hash(), password)
        return None
    if not check_password_hash(user.password_hash, password):
        return None
    return user


def create_access_token(user):
    """Return (token, lifetime_in_seconds). "sub" must be a string (PyJWT 2.10+)."""
    lifetime = current_app.config["TOKEN_TTL_MINUTES"] * 60
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user.id), "iat": now, "exp": now + timedelta(seconds=lifetime)}
    token = jwt.encode(payload, current_app.config["JWT_SECRET"], algorithm="HS256")
    return token, lifetime


def _bearer_token():
    header = request.headers.get("Authorization", "").strip()
    if not header:
        raise APIError(
            401, "missing_token",
            "Log in first, then send the header 'Authorization: Bearer <token>'.",
        )
    scheme, _, token = header.partition(" ")
    token = token.strip()
    if scheme.lower() != "bearer" or not token:
        raise APIError(
            401, "invalid_token",
            "The Authorization header must look like 'Bearer <token>'.",
        )
    return token


def auth_required(view):
    """Reject the request with 401 unless it carries a valid token.

    On success the logged-in user is available as g.current_user.
    """

    @wraps(view)
    def wrapper(*args, **kwargs):
        token = _bearer_token()
        try:
            payload = jwt.decode(
                token,
                current_app.config["JWT_SECRET"],
                algorithms=["HS256"],
                options={"require": ["exp", "sub"]},
            )
            user_id = int(payload["sub"])  # the token stores it as a string
        except jwt.ExpiredSignatureError:
            raise APIError(401, "token_expired", "Your session has expired. Log in again.")
        except (jwt.InvalidTokenError, ValueError):
            raise APIError(401, "invalid_token", "The token is not valid. Log in again.")

        user = db.session.get(User, user_id)
        if user is None:
            raise APIError(401, "invalid_token", "The token's user no longer exists. Log in again.")
        g.current_user = user
        return view(*args, **kwargs)

    return wrapper
