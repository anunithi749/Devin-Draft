"""Integration tests for the API, agent flow, and approval gate."""

import pytest

from app import create_app
from app.models import db
from app.agent import MockIntakeAgent, looks_quantified


@pytest.fixture
def client():
    app = create_app({"TESTING": True,
                       "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    with app.app_context():
        db.create_all()
    with app.test_client() as c:
        yield c


# -- agent unit tests ----------------------------------------------------

def test_quantified_detector():
    assert looks_quantified("cut build time from 40 to 12 minutes")
    assert looks_quantified("saved 5 hours a week")
    assert not looks_quantified("improves productivity")
    assert not looks_quantified("makes things better")


def test_mock_agent_full_course_flow():
    agent = MockIntakeAgent()
    state = {"field": "name", "answers": {}}

    steps = ["Priya", "Payments", "AI Fluency",
             "Earned a certification", "AWS ML cert",
             "Passed the exam", "https://cert.example/123"]
    reply = None
    for msg in steps:
        reply = agent.step(state, msg)
        if not reply.done:
            state["field"] = reply.field
    assert reply.done
    assert reply.submission["activity_type"] == "certification"
    assert reply.submission["track"] == "AI Fluency"


def test_mock_agent_pushes_back_on_vague_poc_value():
    agent = MockIntakeAgent()
    state = {"field": "name", "answers": {}}
    for msg in ["Sam", "Web", "AI POC", "Demoed a working POC",
                "Test bot", "It runs in CI"]:
        reply = agent.step(state, msg)
        if not reply.done:
            state["field"] = reply.field

    # Now at business_value; a vague answer must be rejected
    reply = agent.step(state, "it improves productivity")
    assert reply.field == "business_value"
    assert "vague" in reply.message.lower() or "number" in reply.message.lower()

    # A quantified answer is accepted and advances
    reply = agent.step(state, "cut CI reruns from 40/day to 0")
    assert reply.field == "evidence_url"


# -- API tests -----------------------------------------------------------

def test_create_submission_defaults_to_pending(client):
    res = client.post("/api/submissions", json={
        "name": "Meera", "team": "Data", "activity_type": "poc_demoed",
        "title": "Redaction", "impact_measured": True,
    })
    assert res.status_code == 201
    body = res.get_json()
    assert body["status"] == "Pending"
    assert body["points"] == 110
    assert body["track"] == "AI POC"


def test_bad_activity_type_rejected(client):
    res = client.post("/api/submissions", json={
        "name": "X", "activity_type": "sleeping", "title": "z",
    })
    assert res.status_code == 400


def test_pending_entries_stay_off_leaderboard(client):
    client.post("/api/submissions", json={
        "name": "Meera", "activity_type": "poc_demoed",
        "title": "Redaction", "impact_measured": True,
    })
    board = client.get("/api/leaderboard").get_json()
    assert board == []  # still Pending, not counted


def test_approval_puts_entry_on_leaderboard(client):
    created = client.post("/api/submissions", json={
        "name": "Meera", "activity_type": "poc_demoed",
        "title": "Redaction", "impact_measured": True,
    }).get_json()

    client.post(f"/api/submissions/{created['id']}/status",
                json={"status": "Approved"})

    board = client.get("/api/leaderboard").get_json()
    assert len(board) == 1
    assert board[0]["name"] == "Meera"
    assert board[0]["total_points"] == 110


def test_agent_start_and_message_endpoints(client):
    start = client.post("/api/agent/start").get_json()
    assert "name" in start["message"].lower() or start["message"]
    step = client.post("/api/agent/message",
                       json={"message": "Priya"}).get_json()
    assert step["message"]  # asks the next question


def test_pages_render(client):
    for path in ("/", "/board", "/submit", "/review"):
        assert client.get(path).status_code == 200
