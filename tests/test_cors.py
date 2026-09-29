from conftest import assert_error

VITE = "http://localhost:5173"


def preflight(client, path, method, headers="authorization, content-type", origin=VITE):
    return client.options(path, headers={
        "Origin": origin,
        "Access-Control-Request-Method": method,
        "Access-Control-Request-Headers": headers,
    })


def test_allowed_origin_gets_the_header(client):
    response = client.get("/health", headers={"Origin": VITE})
    assert response.status_code == 200
    assert response.headers["Access-Control-Allow-Origin"] == VITE


def test_preflight_for_authorization_header(client):
    response = preflight(client, "/tasks", "POST")
    assert response.status_code == 200
    assert response.headers["Access-Control-Allow-Origin"] == VITE
    allowed_headers = response.headers["Access-Control-Allow-Headers"].lower()
    assert "authorization" in allowed_headers and "content-type" in allowed_headers
    allowed_methods = response.headers["Access-Control-Allow-Methods"]
    for method in ("GET", "POST", "PATCH", "DELETE", "OPTIONS"):
        assert method in allowed_methods


def test_preflight_for_patch_and_delete_on_an_item(client):
    for method in ("PATCH", "DELETE"):
        response = preflight(client, "/tasks/1", method)
        assert response.status_code == 200
        assert response.headers["Access-Control-Allow-Origin"] == VITE
        assert method in response.headers["Access-Control-Allow-Methods"]


def test_preflight_does_not_need_a_token(client):
    # Browsers never send the Authorization header on a preflight.
    response = preflight(client, "/users/me", "GET", headers="authorization")
    assert response.status_code == 200


def test_disallowed_origin_gets_no_header(client):
    response = client.get("/health", headers={"Origin": "http://evil.example.com"})
    assert "Access-Control-Allow-Origin" not in response.headers
    response = preflight(client, "/tasks", "POST", origin="http://evil.example.com")
    assert "Access-Control-Allow-Origin" not in response.headers


def test_127_0_0_1_is_a_different_origin(client):
    response = client.get("/health", headers={"Origin": "http://127.0.0.1:5173"})
    assert "Access-Control-Allow-Origin" not in response.headers


def test_error_responses_carry_cors_headers_too(client):
    # Otherwise the browser hides the 401 body from the frontend.
    response = client.get("/users/me", headers={"Origin": VITE})
    assert_error(response, 401, "missing_token")
    assert response.headers["Access-Control-Allow-Origin"] == VITE
    response = client.get("/nope", headers={"Origin": VITE})
    assert_error(response, 404, "not_found")
    assert response.headers["Access-Control-Allow-Origin"] == VITE
