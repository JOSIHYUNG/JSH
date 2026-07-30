import time

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.db import engine
from app.integrations.openai.responses import OpenAIResponsesGateway
from app.main import app
from app.models import ChatConversation, QuestionHistory


client = TestClient(app)


def wait_question(question_id: int) -> dict:
    for _ in range(40):
        response = client.get(f"/api/v1/questions/{question_id}")
        assert response.status_code == 200
        result = response.json()["data"]
        if result["status"] in {"completed", "no_evidence", "failed"}:
            return result
        time.sleep(0.025)
    raise AssertionError("question did not reach a terminal state")


def test_follow_up_question_keeps_conversation_context_and_turn_sources() -> None:
    document = client.post(
        "/api/v1/documents",
        json={"title": "Chat context", "content": "Sensors support situational awareness in the aircraft."},
    )
    assert document.status_code == 202

    conversation = client.post("/api/v1/conversations", json={"title": "Context test"})
    assert conversation.status_code == 201
    conversation_id = conversation.json()["data"]["id"]

    with Session(engine) as session:
        stored = session.get(ChatConversation, conversation_id)
        assert stored is not None
        stored.turn_count = 1
        session.add(
            QuestionHistory(
                conversation_id=conversation_id,
                turn_index=1,
                question="항공기의 센서 역할은 무엇인가요?",
                status="completed",
                answer_markdown="센서는 상황 인식을 지원합니다. [S1]",
            )
        )
        session.add(stored)
        session.commit()

    response = client.post(
        f"/api/v1/conversations/{conversation_id}/questions",
        json={"question": "그 기능을 더 짧게 설명해줘"},
    )
    assert response.status_code == 202
    turn = wait_question(response.json()["data"]["id"])

    assert turn["conversation_id"] == conversation_id
    assert turn["turn_index"] == 2
    assert turn["context"]["turn_count"] == 1
    assert "항공기의 센서 역할" in turn["context"]["retrieval_query"]
    assert turn["status"] == "failed"
    assert turn["sources"]

    detail = client.get(f"/api/v1/conversations/{conversation_id}")
    assert detail.status_code == 200
    assert len(detail.json()["data"]["turns"]) == 2
    assert detail.json()["data"]["turns"][1]["sources"][0]["citation_key"] == "S1"


def test_conversation_rename_and_delete_isolated_from_documents() -> None:
    conversation = client.post("/api/v1/conversations", json={"title": "Before rename"})
    conversation_id = conversation.json()["data"]["id"]

    renamed = client.patch(f"/api/v1/conversations/{conversation_id}", json={"title": "After rename"})
    assert renamed.status_code == 200
    assert renamed.json()["data"]["title"] == "After rename"

    deleted = client.delete(f"/api/v1/conversations/{conversation_id}")
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/conversations/{conversation_id}").status_code == 404


def test_no_evidence_generates_general_answer_and_ai_document_node(monkeypatch) -> None:
    monkeypatch.setattr(OpenAIResponsesGateway, "configured", property(lambda _self: True))
    monkeypatch.setattr(
        OpenAIResponsesGateway,
        "general_answer",
        lambda _self, _question, _turns: "저장된 자료 밖의 일반 AI 답변입니다. 지구는 태양 주위를 공전합니다.",
    )

    response = client.post("/api/v1/questions", json={"question": "저장된 자료에 없는 우주 질문"})
    assert response.status_code == 202
    result = wait_question(response.json()["data"]["id"])

    assert result["status"] == "completed"
    assert result["answer_mode"] == "general"
    assert result["generated_document"]["source_type"] == "ai_generated"
    assert result["generated_document"]["status"] == "ready"

    graph = client.get("/api/v1/graph")
    assert graph.status_code == 200
    assert any(node["entity_type"] == "document" and node["entity_id"] == result["generated_document"]["id"] for node in graph.json()["data"]["nodes"])
