import pytest

from conftest import assert_error

TASK_KEYS = {"id", "title", "description", "done", "due_date", "created_at", "owner_id"}


def create_task(client, headers, **fields):
    body = {"title": "A task"}
    body.update(fields)
    response = client.post("/tasks", headers=headers, json=body)
    assert response.status_code == 201, response.get_json()
    return response.get_json()


# CRUD ------------------------------------------------------------------------

def test_crud_happy_path(client, signup):
    headers = signup()
    me = client.get("/users/me", headers=headers).get_json()

    # Create: owner_id comes from the token, never from the body.
    response = client.post("/tasks", headers=headers, json={
        "title": "  Write the endpoint map  ",
        "description": "Screen -> method, path, request, response",
        "due_date": "2026-10-15",
        "owner_id": 999,
        "id": 12345,
    })
    assert response.status_code == 201
    task = response.get_json()
    assert set(task) == TASK_KEYS
    assert task["title"] == "Write the endpoint map"
    assert task["done"] is False
    assert task["due_date"] == "2026-10-15"
    assert task["owner_id"] == me["id"]
    assert task["id"] != 12345
    assert task["created_at"].endswith("Z")

    # Read
    response = client.get(f"/tasks/{task['id']}", headers=headers)
    assert response.status_code == 200
    assert response.get_json() == task

    # Update (partial)
    response = client.patch(f"/tasks/{task['id']}", headers=headers, json={"done": True})
    assert response.status_code == 200
    updated = response.get_json()
    assert updated["done"] is True
    assert updated["title"] == task["title"]

    response = client.patch(f"/tasks/{task['id']}", headers=headers,
                            json={"title": "Renamed", "description": "", "due_date": None})
    assert response.status_code == 200
    updated = response.get_json()
    assert (updated["title"], updated["description"], updated["due_date"]) == ("Renamed", None, None)

    # List
    listing = client.get("/tasks", headers=headers).get_json()
    assert [item["id"] for item in listing["items"]] == [task["id"]]

    # Delete
    response = client.delete(f"/tasks/{task['id']}", headers=headers)
    assert response.status_code == 204
    assert response.data == b""
    assert_error(client.get(f"/tasks/{task['id']}", headers=headers), 404, "not_found")


def test_tasks_require_a_token(client):
    assert_error(client.get("/tasks"), 401, "missing_token")
    assert_error(client.post("/tasks", json={"title": "x"}), 401, "missing_token")
    assert_error(client.get("/tasks/1"), 401, "missing_token")
    assert_error(client.patch("/tasks/1", json={"done": True}), 401, "missing_token")
    assert_error(client.delete("/tasks/1"), 401, "missing_token")


# Validation ------------------------------------------------------------------

def test_create_requires_title(client, signup):
    error = assert_error(client.post("/tasks", headers=signup(), json={}), 400, "validation_error")
    assert error["fields"] == {"title": "is required"}


@pytest.mark.parametrize("body, field, message", [
    ({"title": "   "}, "title", "cannot be blank"),
    ({"title": "x" * 121}, "title", "must be at most 120 characters"),
    ({"title": 42}, "title", "must be a string"),
    ({"title": "ok", "description": "x" * 1001}, "description", "must be at most 1000 characters"),
    ({"title": "ok", "done": "yes"}, "done", "must be true or false"),
    ({"title": "ok", "done": 1}, "done", "must be true or false"),
    ({"title": "ok", "due_date": "15/10/2026"}, "due_date", "must be a date in YYYY-MM-DD format, or null"),
    ({"title": "ok", "due_date": "2026-02-30"}, "due_date", "must be a real calendar date in YYYY-MM-DD format"),
])
def test_create_validation_errors(client, signup, body, field, message):
    error = assert_error(client.post("/tasks", headers=signup(), json=body), 400, "validation_error")
    assert error["fields"] == {field: message}


def test_create_reports_every_bad_field_at_once(client, signup):
    body = {"title": "", "done": "no", "due_date": "tomorrow"}
    error = assert_error(client.post("/tasks", headers=signup(), json=body), 400, "validation_error")
    assert set(error["fields"]) == {"title", "done", "due_date"}


def test_create_accepts_limits(client, signup):
    task = create_task(client, signup(), title="x" * 120, description="d" * 1000, due_date="")
    assert len(task["title"]) == 120 and task["due_date"] is None


def test_patch_validation(client, signup):
    headers = signup()
    task = create_task(client, headers)
    error = assert_error(client.patch(f"/tasks/{task['id']}", headers=headers, json={"title": ""}),
                         400, "validation_error")
    assert error["fields"] == {"title": "cannot be blank"}
    # Nothing to update
    assert_error(client.patch(f"/tasks/{task['id']}", headers=headers, json={"owner_id": 5}),
                 400, "validation_error")
    # The task is unchanged
    assert client.get(f"/tasks/{task['id']}", headers=headers).get_json() == task


# Pagination ------------------------------------------------------------------

@pytest.fixture
def twenty_five_tasks(client, signup):
    headers = signup()
    ids = [create_task(client, headers, title=f"Task {n}")["id"] for n in range(1, 26)]
    # Another user's tasks must never show up in alice's list.
    other = signup("bob", "bob-password-1")
    for n in range(3):
        create_task(client, other, title=f"Bob {n}")
    return headers, ids


def test_pagination_metadata(client, twenty_five_tasks):
    headers, ids = twenty_five_tasks
    body = client.get("/tasks?page=1&per_page=10", headers=headers).get_json()
    assert {k: body[k] for k in ("page", "per_page", "total", "pages")} == {
        "page": 1, "per_page": 10, "total": 25, "pages": 3}
    assert [t["id"] for t in body["items"]] == ids[:10]

    body = client.get("/tasks?page=3&per_page=10", headers=headers).get_json()
    assert [t["id"] for t in body["items"]] == ids[20:]
    assert body["page"] == 3 and body["pages"] == 3


def test_pagination_defaults(client, twenty_five_tasks):
    headers, _ = twenty_five_tasks
    body = client.get("/tasks", headers=headers).get_json()
    assert (body["page"], body["per_page"], body["total"], body["pages"]) == (1, 10, 25, 3)
    assert len(body["items"]) == 10


def test_page_past_the_end_is_empty_not_an_error(client, twenty_five_tasks):
    headers, _ = twenty_five_tasks
    response = client.get("/tasks?page=4&per_page=10", headers=headers)
    assert response.status_code == 200
    body = response.get_json()
    assert body["items"] == []
    assert (body["page"], body["total"], body["pages"]) == (4, 25, 3)
    huge = client.get("/tasks?page=99999999999999999999", headers=headers)
    assert huge.status_code == 200 and huge.get_json()["items"] == []


def test_per_page_max_is_50(client, twenty_five_tasks):
    headers, _ = twenty_five_tasks
    body = client.get("/tasks?per_page=50", headers=headers).get_json()
    assert len(body["items"]) == 25 and body["pages"] == 1


@pytest.mark.parametrize("query, field", [
    ("per_page=0", "per_page"),
    ("per_page=51", "per_page"),
    ("per_page=abc", "per_page"),
    ("per_page=", "per_page"),
    ("per_page=2.5", "per_page"),
    ("page=0", "page"),
    ("page=-1", "page"),
    ("page=abc", "page"),
])
def test_bad_pagination_params_are_400(client, signup, query, field):
    error = assert_error(client.get(f"/tasks?{query}", headers=signup()), 400, "validation_error")
    assert set(error["fields"]) == {field}


def test_empty_list(client, signup):
    body = client.get("/tasks", headers=signup()).get_json()
    assert body == {"items": [], "page": 1, "per_page": 10, "total": 0, "pages": 0}


# Ownership: 403 for someone else's task, 404 for a missing one ---------------

def test_other_users_task_is_403_for_get_patch_delete(client, signup):
    owner = signup("bob", "bob-password-1")
    task = create_task(client, owner, title="Bob's task")
    intruder = signup("alice")

    assert_error(client.get(f"/tasks/{task['id']}", headers=intruder), 403, "forbidden")
    assert_error(client.patch(f"/tasks/{task['id']}", headers=intruder, json={"done": True}),
                 403, "forbidden")
    assert_error(client.delete(f"/tasks/{task['id']}", headers=intruder), 403, "forbidden")

    # Nothing changed for the owner.
    assert client.get(f"/tasks/{task['id']}", headers=owner).get_json() == task


def test_missing_task_is_404(client, signup):
    headers = signup()
    assert_error(client.get("/tasks/999", headers=headers), 404, "not_found")
    assert_error(client.patch("/tasks/999", headers=headers, json={"done": True}), 404, "not_found")
    assert_error(client.delete("/tasks/999", headers=headers), 404, "not_found")
