from datetime import datetime, timedelta, timezone

import jwt

from conftest import assert_error
from taskapi.extensions import db
from taskapi.models import User


def login(client, username="alice", password="alice-password-1"):
    return client.post("/auth/login", json={"username": username, "password": password})


# Register --------------------------------------------------------------------

def test_register_success(client):
    response = client.post("/auth/register", json={"username": "alice", "password": "alice-password-1"})
    assert response.status_code == 201
    body = response.get_json()
    assert body == {"id": body["id"], "username": "alice"}
    assert isinstance(body["id"], int)


def test_register_stores_only_a_hash(client, app):
    client.post("/auth/register", json={"username": "alice", "password": "alice-password-1"})
    user = db.session.execute(db.select(User).filter_by(username="alice")).scalar_one()
    assert user.password_hash != "alice-password-1"
    assert "alice-password-1" not in user.password_hash


def test_register_validation_lists_each_field(client):
    response = client.post("/auth/register", json={"username": "al", "password": "short"})
    error = assert_error(response, 400, "validation_error")
    assert error["fields"] == {
        "username": "must be between 3 and 30 characters",
        "password": "must be at least 8 characters",
    }


def test_register_missing_fields(client):
    error = assert_error(client.post("/auth/register", json={}), 400, "validation_error")
    assert error["fields"] == {"username": "is required", "password": "is required"}


def test_register_username_too_long(client):
    response = client.post("/auth/register", json={"username": "a" * 31, "password": "long-enough-1"})
    error = assert_error(response, 400, "validation_error")
    assert set(error["fields"]) == {"username"}


def test_register_duplicate_username_is_409(client):
    body = {"username": "alice", "password": "alice-password-1"}
    assert client.post("/auth/register", json=body).status_code == 201
    assert_error(client.post("/auth/register", json=body), 409, "username_taken")


# Login -----------------------------------------------------------------------

def test_login_success(client, app):
    client.post("/auth/register", json={"username": "alice", "password": "alice-password-1"})
    response = login(client)
    assert response.status_code == 200
    body = response.get_json()
    assert set(body) == {"access_token", "token_type", "expires_in"}
    assert body["token_type"] == "Bearer"
    assert body["expires_in"] == 60 * 60
    claims = jwt.decode(body["access_token"], app.config["JWT_SECRET"], algorithms=["HS256"])
    assert isinstance(claims["sub"], str)  # PyJWT 2.10+ requires a string sub


def test_login_wrong_password_and_unknown_user_look_the_same(client):
    client.post("/auth/register", json={"username": "alice", "password": "alice-password-1"})
    wrong_password = login(client, password="not-the-password")
    unknown_user = login(client, username="nobody")
    assert_error(wrong_password, 401, "invalid_credentials")
    assert_error(unknown_user, 401, "invalid_credentials")
    assert wrong_password.get_json() == unknown_user.get_json()


def test_login_missing_fields_is_400(client):
    error = assert_error(client.post("/auth/login", json={}), 400, "validation_error")
    assert set(error["fields"]) == {"username", "password"}


# /users/me and tokens --------------------------------------------------------

def test_me_without_token_is_401(client):
    assert_error(client.get("/users/me"), 401, "missing_token")


def test_me_with_wrong_scheme_is_401(client):
    assert_error(client.get("/users/me", headers={"Authorization": "Token abc"}), 401, "invalid_token")


def test_me_with_bearer_null_is_401(client):
    # What a frontend sends when it forgets to check for a missing token.
    assert_error(client.get("/users/me", headers={"Authorization": "Bearer null"}), 401, "invalid_token")


def test_me_with_tampered_token_is_401(client, signup):
    token = signup()["Authorization"].split(" ", 1)[1]
    header, payload, signature = token.split(".")
    tampered = ".".join([header, payload, signature[:-2] + ("AA" if signature[-2:] != "AA" else "BB")])
    response = client.get("/users/me", headers={"Authorization": "Bearer " + tampered})
    assert_error(response, 401, "invalid_token")


def test_me_with_token_signed_by_another_secret_is_401(client, signup):
    signup()
    forged = jwt.encode(
        {"sub": "1", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        "some-other-secret-that-is-also-32-bytes-long", algorithm="HS256",
    )
    assert_error(client.get("/users/me", headers={"Authorization": "Bearer " + forged}), 401, "invalid_token")


def test_me_with_expired_token_is_401_token_expired(client, app, signup):
    signup()
    expired = jwt.encode(
        {"sub": "1", "exp": datetime.now(timezone.utc) - timedelta(seconds=30)},
        app.config["JWT_SECRET"], algorithm="HS256",
    )
    response = client.get("/users/me", headers={"Authorization": "Bearer " + expired})
    assert_error(response, 401, "token_expired")


def test_me_with_integer_sub_is_401(client, app, signup):
    signup()
    token = jwt.encode(
        {"sub": 1, "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        app.config["JWT_SECRET"], algorithm="HS256",
    )
    assert_error(client.get("/users/me", headers={"Authorization": "Bearer " + token}), 401, "invalid_token")


def test_me_for_deleted_user_is_401(client, app, signup):
    headers = signup()
    db.session.delete(db.session.execute(db.select(User)).scalar_one())
    db.session.commit()
    assert_error(client.get("/users/me", headers=headers), 401, "invalid_token")


def test_me_with_valid_token(client, signup):
    response = client.get("/users/me", headers=signup())
    assert response.status_code == 200
    body = response.get_json()
    assert body == {"id": body["id"], "username": "alice", "display_name": None}


def test_patch_me_sets_and_clears_display_name(client, signup):
    headers = signup()
    response = client.patch("/users/me", headers=headers, json={"display_name": "  Alice A.  "})
    assert response.status_code == 200
    assert response.get_json()["display_name"] == "Alice A."
    assert client.get("/users/me", headers=headers).get_json()["display_name"] == "Alice A."

    response = client.patch("/users/me", headers=headers, json={"display_name": None})
    assert response.status_code == 200
    assert response.get_json()["display_name"] is None


def test_patch_me_ignores_other_fields(client, signup):
    headers = signup()
    response = client.patch("/users/me", headers=headers,
                            json={"display_name": "Alice", "username": "mallory"})
    assert response.status_code == 200
    assert response.get_json()["username"] == "alice"


def test_patch_me_validation(client, signup):
    headers = signup()
    error = assert_error(client.patch("/users/me", headers=headers, json={}), 400, "validation_error")
    assert error["fields"] == {"display_name": "is required"}
    error = assert_error(client.patch("/users/me", headers=headers, json={"display_name": "x" * 61}),
                         400, "validation_error")
    assert error["fields"] == {"display_name": "must be at most 60 characters"}


def test_patch_me_without_token_is_401(client):
    assert_error(client.patch("/users/me", json={"display_name": "x"}), 401, "missing_token")
