from conftest import assert_error


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_unknown_route_is_json_404(client):
    response = client.get("/no-such-route")
    error = assert_error(response, 404, "not_found")
    assert "GET /no-such-route" in error["message"]
    assert b"<html" not in response.data.lower()


def test_wrong_method_is_json_405(client):
    response = client.post("/health")
    error = assert_error(response, 405, "method_not_allowed")
    assert "GET" in response.headers["Allow"]
    assert "Allowed:" in error["message"]
    assert b"<html" not in response.data.lower()


def test_wrong_method_on_task_item(client):
    assert_error(client.put("/tasks/1"), 405, "method_not_allowed")


def test_non_numeric_task_id_is_json_404(client, signup):
    assert_error(client.get("/tasks/abc", headers=signup()), 404, "not_found")


def test_body_that_is_not_json(client):
    # The classic frontend bug: forgetting Content-Type: application/json.
    response = client.post("/auth/register", data='{"username": "alice"}')
    assert_error(response, 400, "invalid_json")


def test_json_array_body_is_rejected(client):
    assert_error(client.post("/auth/register", json=["alice"]), 400, "invalid_json")


def test_body_too_large_is_json_413(client):
    response = client.post("/auth/register", data="x" * (1024 * 1024 + 1),
                           content_type="application/json")
    assert_error(response, 413, "request_entity_too_large")


def test_unexpected_exception_is_json_500(app):
    @app.get("/boom")
    def boom():
        raise RuntimeError("unexpected")

    app.config["PROPAGATE_EXCEPTIONS"] = False  # behave like production
    response = app.test_client().get("/boom")
    assert_error(response, 500, "internal_error")
