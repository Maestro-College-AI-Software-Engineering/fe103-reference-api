import pytest

from taskapi import create_app
from taskapi.config import ProductionConfig, normalize_database_url, parse_origins
from taskapi.extensions import db
from taskapi.models import Task, User


def count(model):
    return db.session.scalar(db.select(db.func.count()).select_from(model))


def test_init_db_command(app):
    result = app.test_cli_runner().invoke(args=["init-db"])
    assert result.exit_code == 0, result.output
    assert "ready" in result.output


def test_seed_is_idempotent_and_gives_three_pages(app, client):
    runner = app.test_cli_runner()
    first = runner.invoke(args=["seed"])
    assert first.exit_code == 0, first.output
    assert "demo: created" in first.output and "other: created" in first.output
    second = runner.invoke(args=["seed"])
    assert second.exit_code == 0, second.output
    assert "already exists" in second.output
    assert count(User) == 2 and count(Task) == 28

    token = client.post("/auth/login", json={"username": "demo", "password": "demo-password-1"}
                        ).get_json()["access_token"]
    headers = {"Authorization": "Bearer " + token}
    page1 = client.get("/tasks?page=1&per_page=10", headers=headers).get_json()
    page3 = client.get("/tasks?page=3&per_page=10", headers=headers).get_json()
    assert (page1["total"], page1["pages"], len(page1["items"])) == (25, 3, 10)
    assert len(page3["items"]) == 5
    assert any(t["done"] for t in page1["items"]) and not all(t["done"] for t in page1["items"])
    assert any(t["due_date"] for t in page1["items"])

    # demo gets 403 on other's tasks
    other = client.post("/auth/login", json={"username": "other", "password": "other-password-1"})
    other_headers = {"Authorization": "Bearer " + other.get_json()["access_token"]}
    other_task_id = client.get("/tasks", headers=other_headers).get_json()["items"][0]["id"]
    assert client.get(f"/tasks/{other_task_id}", headers=headers).status_code == 403


def test_seed_reset_restores_the_demo_data(app, client):
    runner = app.test_cli_runner()
    runner.invoke(args=["seed"])
    demo = db.session.execute(db.select(User).filter_by(username="demo")).scalar_one()
    db.session.delete(demo.tasks[0])
    db.session.commit()
    assert count(Task) == 27
    result = runner.invoke(args=["seed", "--reset"])
    assert result.exit_code == 0, result.output
    assert count(User) == 2 and count(Task) == 28


def test_parse_origins():
    assert parse_origins(" http://localhost:5173/ , https://my-app.onrender.com,, ") == [
        "http://localhost:5173", "https://my-app.onrender.com"]


@pytest.mark.parametrize("url, expected", [
    ("postgres://u:p@host:5432/db", "postgresql+psycopg://u:p@host:5432/db"),
    ("postgresql://u:p@host/db?sslmode=require", "postgresql+psycopg://u:p@host/db?sslmode=require"),
    ("postgresql+psycopg://u:p@db:5432/db", "postgresql+psycopg://u:p@db:5432/db"),
    ("sqlite:///taskapi.db", "sqlite:///taskapi.db"),
    (None, None),
])
def test_normalize_database_url(url, expected):
    assert normalize_database_url(url) == expected


def test_production_refuses_to_start_without_secrets(monkeypatch):
    monkeypatch.setattr(ProductionConfig, "SQLALCHEMY_DATABASE_URI", None)
    monkeypatch.setattr(ProductionConfig, "JWT_SECRET", None)
    with pytest.raises(RuntimeError, match="DATABASE_URL, JWT_SECRET"):
        create_app("production")


def test_unknown_config_name():
    with pytest.raises(RuntimeError, match="Unknown config"):
        create_app("staging")
