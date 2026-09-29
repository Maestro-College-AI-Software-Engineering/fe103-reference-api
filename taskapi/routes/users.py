from flask import Blueprint, g

from ..errors import ValidationError
from ..extensions import db
from ..security import auth_required
from ..validation import check_display_name, get_json_object

bp = Blueprint("users", __name__, url_prefix="/users")


@bp.get("/me")
@auth_required
def get_me():
    return g.current_user.to_dict()


@bp.patch("/me")
@auth_required
def update_me():
    """Only display_name can change here; other keys in the body are ignored."""
    data = get_json_object()
    if "display_name" not in data:
        raise ValidationError({"display_name": "is required"})
    display_name, error = check_display_name(data["display_name"])
    if error:
        raise ValidationError({"display_name": error})

    g.current_user.display_name = display_name
    db.session.commit()
    return g.current_user.to_dict()
