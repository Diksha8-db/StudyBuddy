"""
Unit tests for StudyBuddy MCP Server HTTP endpoints and tool schemas.
"""

import pytest
from starlette.testclient import TestClient
from server import app, mcp


@pytest.fixture
def client():
    return TestClient(app)


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "studybuddy-mcp"
    assert data["mcp_endpoint"] == "/mcp"
    assert "tools" in data
    assert "start_quiz" in data["tools"]
    assert "grade_answer" in data["tools"]


def test_root_redirect(client):
    response = client.get("/", follow_redirects=False)
    assert response.status_code in (302, 307)
    assert response.headers["location"] == "/simulator/"


def test_simulator_decks(client):
    response = client.get("/api/simulator/decks")
    assert response.status_code == 200
    data = response.json()
    assert "decks" in data
    assert len(data["decks"]) >= 1


def test_simulator_chat_flow(client):
    # 1. Ask to quiz on Physics Chapter 3
    response = client.post("/api/simulator/chat", json={"message": "Quiz me on Physics Chapter 3"})
    assert response.status_code == 200
    data = response.json()
    assert "speech" in data
    assert "Question 1:" in data["speech"]
    assert data["active_session"] is not None
    assert data["tool_call"]["name"] == "start_quiz"

    session_id = data["active_session"]["session_id"]
    card_id = data["active_session"]["card_id"]

    # 2. Answer question
    ans_response = client.post(
        "/api/simulator/chat",
        json={
            "message": "Force equals mass times acceleration",
            "session_id": session_id,
            "card_id": card_id,
        },
    )
    assert ans_response.status_code == 200
    ans_data = ans_response.json()
    assert "speech" in ans_data
    assert ans_data["tool_call"]["name"] == "grade_answer"


def test_mcp_tools_registration():
    import asyncio
    tools = asyncio.run(mcp.list_tools())
    tool_names = [t.name for t in tools]
    expected = [
        "add_flashcard",
        "list_decks",
        "start_quiz",
        "grade_answer",
        "get_weak_topics",
        "schedule_review",
    ]
    for exp in expected:
        assert exp in tool_names
