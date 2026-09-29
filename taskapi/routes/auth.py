from flask import Blueprint
from sqlalchemy.exc import IntegrityError

from ..errors import APIError, ValidationError
from ..extensions import db
from ..models import User
from ..security import authenticate, create_access_token, hash_password
from ..validation import check_password, check_username, get_json_object

bp = Blueprint("auth", __name__, url_prefix="/auth")


def _username_taken(username):
    return APIError(409, "username_taken", f"The username '{username}' is already taken.")


@bp.post("/register")
def register():
    data = get_json_object()
    username, username_error = check_username(data.get("username"))
    password, password_error = check_password(data.get("password"))
    errors = {"username": username_error, "password": password_error}
    errors = {field: message for field, message in errors.items() if message}
    if errors:
        raise ValidationError(errors)

    if db.session.execute(db.select(User.id).filter_by(username=username)).first():
        raise _username_taken(username)

    user = User(username=username, password_hash=hash_password(password))
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:  # someone registered the same name a moment ago
        db.session.rollback()
        raise _username_taken(username)
    return {"id": user.id, "username": user.username}, 201


@bp.post("/login")
def login():
    data = get_json_object()
    username = data.get("username")
    password = data.get("password")
    errors = {}
    if not isinstance(username, str) or not username.strip():
        errors["username"] = "is required"
    if not isinstance(password, str) or not password:
        errors["password"] = "is required"
    if errors:
        raise ValidationError(errors)

    user = authenticate(username.strip(), password)
    if user is None:
        # Same answer for an unknown username and a wrong password.
        raise APIError(401, "invalid_credentials", "Incorrect username or password.")

    token, expires_in = create_access_token(user)
    return {"access_token": token, "token_type": "Bearer", "expires_in": expires_in}
