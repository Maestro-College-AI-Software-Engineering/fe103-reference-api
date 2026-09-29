from flask import Blueprint, g

from ..errors import APIError, ValidationError
from ..extensions import db
from ..models import Task
from ..security import auth_required
from ..validation import get_json_object, query_int, validate_task

bp = Blueprint("tasks", __name__, url_prefix="/tasks")

MAX_PER_PAGE = 50


def get_owned_task(task_id):
    """The caller's task, or 404 if it does not exist, or 403 if it is someone else's.

    This API chose 403 for other users' tasks. Some APIs answer 404 instead, so
    they do not even reveal that the id exists; a frontend should handle both.
    """
    task = db.session.get(Task, task_id)
    if task is None:
        raise APIError(404, "not_found", f"Task {task_id} does not exist.")
    if task.owner_id != g.current_user.id:
        raise APIError(403, "forbidden", "This task belongs to another user.")
    return task


@bp.get("")
@auth_required
def list_tasks():
    page, page_error = query_int("page", default=1)
    per_page, per_page_error = query_int("per_page", default=10, maximum=MAX_PER_PAGE)
    errors = {"page": page_error, "per_page": per_page_error}
    errors = {field: message for field, message in errors.items() if message}
    if errors:
        raise ValidationError(errors, "Invalid pagination parameters. See 'fields' for details.")

    mine = Task.owner_id == g.current_user.id
    total = db.session.scalar(db.select(db.func.count()).select_from(Task).where(mine))
    pages = (total + per_page - 1) // per_page  # 0 when there are no tasks

    items = []
    if page <= pages:  # a page past the end is an empty list, not an error
        query = (
            db.select(Task)
            .where(mine)
            .order_by(Task.id)
            .limit(per_page)
            .offset((page - 1) * per_page)
        )
        items = db.session.scalars(query).all()

    return {
        "items": [task.to_dict() for task in items],
        "page": page,
        "per_page": per_page,
        "total": total,
        "pages": pages,
    }


@bp.post("")
@auth_required
def create_task():
    values = validate_task(get_json_object(), partial=False)
    task = Task(owner_id=g.current_user.id, **values)  # owner always comes from the token
    db.session.add(task)
    db.session.commit()
    return task.to_dict(), 201


@bp.get("/<int:task_id>")
@auth_required
def get_task(task_id):
    return get_owned_task(task_id).to_dict()


@bp.patch("/<int:task_id>")
@auth_required
def update_task(task_id):
    task = get_owned_task(task_id)
    values = validate_task(get_json_object(), partial=True)
    for name, value in values.items():
        setattr(task, name, value)
    db.session.commit()
    return task.to_dict()


@bp.delete("/<int:task_id>")
@auth_required
def delete_task(task_id):
    task = get_owned_task(task_id)
    db.session.delete(task)
    db.session.commit()
    return "", 204
