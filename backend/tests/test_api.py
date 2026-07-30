import time

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_and_envelope() -> None:
    response = client.get("/api/v1/health", headers={"X-Request-ID": "req_test_health"})
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["status"] == "ok"
    assert body["error"] is None
    assert body["meta"]["request_id"] == "req_test_health"
    assert response.headers["X-Request-ID"] == "req_test_health"


def test_create_document_analysis_graph_and_original() -> None:
    response = client.post("/api/v1/documents", json={"title": "Focus Notes", "content": "# Focus\n\nFastAPI and SQLite support focused knowledge retrieval."})
    assert response.status_code == 202
    document_id = response.json()["data"]["document"]["id"]

    detail = client.get(f"/api/v1/documents/{document_id}")
    assert detail.status_code == 200
    assert detail.json()["data"]["document"]["status"] == "ready"
    assert detail.json()["data"]["document"]["title"] == "Focus Notes"
    assert detail.json()["data"]["chunks"]

    original = client.get(f"/api/v1/documents/{document_id}/original", params={"start_char": 0, "end_char": 7})
    assert original.status_code == 200
    assert original.json()["data"]["highlight_start_char"] == 0

    graph = client.get("/api/v1/graph", params={"include_chunks": True, "node_types": "document,chunk,concept"})
    assert graph.status_code == 200
    assert graph.json()["data"]["node_count"] >= 2

    deleted = client.delete(f"/api/v1/documents/{document_id}")
    assert deleted.status_code == 202


def test_upload_question_history_and_not_found() -> None:
    upload = client.post("/api/v1/documents/upload", files={"file": ("retrieval.md", b"# Retrieval\n\nSQLite FTS5 finds local evidence.", "text/markdown")})
    assert upload.status_code == 202
    document_id = upload.json()["data"]["document"]["id"]

    for _ in range(60):
        detail = client.get(f"/api/v1/documents/{document_id}")
        assert detail.status_code == 200
        if detail.json()["data"]["document"]["status"] in {"ready", "failed"}:
            break
        time.sleep(0.5)
    assert detail.json()["data"]["document"]["status"] == "ready"

    question = client.post("/api/v1/questions", json={"question": "SQLite FTS5"})
    assert question.status_code == 202
    question_id = question.json()["data"]["id"]
    for _ in range(40):
        result = client.get(f"/api/v1/questions/{question_id}").json()["data"]
        if result["status"] in {"completed", "no_evidence", "failed"}:
            break
        time.sleep(0.025)
    assert result["sources"]
    assert len(result["sources"]) <= 3
    assert result["sources"][0]["citation_key"] == "S1"
    assert result["status"] == "failed"
    assert result["answer_markdown"] is None
    assert result["error"]["code"] == "AI_NOT_CONFIGURED"
    assert result["retrieval"]["provider"] == "lexical_fallback"

    history = client.get("/api/v1/questions")
    assert history.status_code == 200
    assert history.json()["data"]["items"]

    missing = client.get("/api/v1/documents/999999")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "DOCUMENT_NOT_FOUND"

    assert client.delete(f"/api/v1/questions/{question_id}").status_code == 204
    assert client.delete(f"/api/v1/documents/{document_id}").status_code == 202


def test_document_update_title_and_content() -> None:
    created = client.post(
        "/api/v1/documents",
        json={"title": "CRUD original", "content": "Original CRUD content.", "auto_analyze": False},
    )
    assert created.status_code == 202
    document_id = created.json()["data"]["document"]["id"]

    updated = client.patch(
        f"/api/v1/documents/{document_id}",
        json={"title": "CRUD updated", "content": "Updated CRUD content.", "auto_analyze": False},
    )
    assert updated.status_code == 202
    assert updated.json()["data"]["document"]["title"] == "CRUD updated"
    assert updated.json()["data"]["document"]["status"] == "draft"
    assert updated.json()["data"]["job"] is None

    detail = client.get(f"/api/v1/documents/{document_id}")
    assert detail.status_code == 200
    assert detail.json()["data"]["document"]["character_count"] == len("Updated CRUD content.")

    deleted = client.delete(f"/api/v1/documents/{document_id}")
    assert deleted.status_code == 202


def test_delete_document_preserves_question_snapshot() -> None:
    created = client.post(
        "/api/v1/documents",
        json={"title": "Snapshot source", "content": "Deletion snapshot evidence stays readable."},
    )
    document_id = created.json()["data"]["document"]["id"]
    question = client.post("/api/v1/questions", json={"question": "snapshot evidence"})
    question_id = question.json()["data"]["id"]

    deleted = client.delete(f"/api/v1/documents/{document_id}")
    assert deleted.status_code == 202
    assert client.get(f"/api/v1/documents/{document_id}").status_code == 404

    restored = client.get(f"/api/v1/questions/{question_id}")
    assert restored.status_code == 200
    source = restored.json()["data"]["sources"][0]
    assert source["openable"] is False
    assert source["document_status"] == "document_deleted"
    assert source["chunk_preview"]


def test_validation_error_does_not_echo_document_content() -> None:
    secret_input = "private-value-that-must-not-be-echoed"
    response = client.post(
        "/api/v1/documents",
        json={"title": "x" * 300, "content": secret_input},
    )
    assert response.status_code == 422
    assert secret_input not in response.text
    assert response.json()["error"]["details"]["fields"]
