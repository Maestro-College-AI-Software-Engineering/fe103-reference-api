import pytest

from taskapi import create_app
from taskapi.extensions import db


@pytest.fixture
def app():
    app = create_app("testing")  # in-memory SQLite, fixed secret
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def signup(client):
    """signup("alice") registers and logs in a user; returns the auth headers."""

    def _signup(username="alice", password="alice-password-1"):
        response = client.post("/auth/register", json={"username": username, "password": password})
        assert response.status_code == 201, response.get_json()
        response = client.post("/auth/login", json={"username": username, "password": password})
        assert response.status_code == 200, response.get_json()
        return {"Authorization": "Bearer " + response.get_json()["access_token"]}

    return _signup


def assert_error(response, status, code):
    """Check the status and the one error shape; return the inner error object."""
    assert response.status_code == status, response.get_data(as_text=True)
    assert response.is_json, f"expected JSON, got {response.content_type}"
    error = response.get_json()["error"]
    assert error["code"] == code
    assert isinstance(error["message"], str) and error["message"]
    return error
