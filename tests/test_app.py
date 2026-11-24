
import pytest
from app import app, init_db


@pytest.fixture
def client():
    app.config["TESTING"] = True
    app.config["DATABASE"] = ":memory:"

    init_db()

    with app.test_client() as client:
        yield client


def test_homepage(client):
    response = client.get("/")
    assert response.status_code == 200


def test_add_task(client):
    response = client.post(
        "/add",
        data={
            "title": "Complete DevOps project",
            "description": "Test task",
            "due_date": "2026-12-01",
            "priority": "High",
            "category": "Projects"
        },
        follow_redirects=True
    )

    assert response.status_code == 200
    assert b"Complete DevOps project" in response.data
