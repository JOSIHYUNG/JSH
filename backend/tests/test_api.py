from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_and_envelope() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["status"] == "ok"
    assert body["error"] is None
    assert body["meta"]["request_id"].startswith("req_")


def test_create_document_analysis_graph_and_original() -> None:
    response = client.post("/api/v1/documents", json={"title": "Focus Notes", "content": "# Focus\n\nFastAPI and SQLite support focused knowledge retrieval."})
    assert response.status_code == 202
    document_id = response.json()["data"]["document"]["id"]

    detail = client.get(f"/api/v1/documents/{document_id}")
    assert detail.status_code == 200
    assert detail.json()["data"]["document"]["status"] == "ready"
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

    question = client.post("/api/v1/questions", json={"question": "SQLite FTS5"})
    assert question.status_code == 201
    result = question.json()["data"]
    question_id = result["id"]
    assert result["sources"]
    assert len(result["sources"]) <= 3
    assert result["sources"][0]["citation_key"] == "S1"

    history = client.get("/api/v1/questions")
    assert history.status_code == 200
    assert history.json()["data"]["items"]

    missing = client.get("/api/v1/documents/999999")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "DOCUMENT_NOT_FOUND"

    assert client.delete(f"/api/v1/questions/{question_id}").status_code == 204
    assert client.delete(f"/api/v1/documents/{document_id}").status_code == 202
