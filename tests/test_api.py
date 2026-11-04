from uuid import uuid4

from fastapi.testclient import TestClient

from cartograph import api


client = TestClient(api.app)


def test_health_check():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_repository_status_returns_not_found(monkeypatch):
    monkeypatch.setattr(api, "load_job", lambda job_id: None)

    response = client.get("/repos/missing-job")

    assert response.status_code == 404
    assert response.json()["detail"] == "Indexing job not found"


def test_ask_rejects_invalid_request():
    response = client.post("/ask", json={})

    assert response.status_code == 422


def test_ask_returns_not_found_for_unknown_repository(monkeypatch):
    monkeypatch.setattr(api, "find_repo_status", lambda repo_id: None)

    response = client.post(
        "/ask",
        json={
            "repo_id": "missing/repository",
            "question": "How does this work?",
            "thread_id": str(uuid4()),
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == (
        "Repository is not registered or indexing has not completed."
    )


def test_ask_returns_conflict_while_indexing(monkeypatch):
    monkeypatch.setattr(
        api,
        "find_repo_status",
        lambda repo_id: {"status": "in_progress"},
    )

    response = client.post(
        "/ask",
        json={
            "repo_id": "owner/repository",
            "question": "How does this work?",
            "thread_id": str(uuid4()),
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Repository indexing status: in_progress"
