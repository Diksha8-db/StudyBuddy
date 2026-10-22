"""
Unit tests for VivaMate viva-practice mode and shared memory.
"""

import os
import tempfile
from unittest.mock import MagicMock, patch
import pytest

from studybuddy.db import Database
from studybuddy.tools import StudyBuddyCore
from studybuddy.evaluator import evaluate_viva_answer_bedrock, is_bedrock_enabled


@pytest.fixture
def viva_core():
    # Use temporary isolated database
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    db = Database(db_path=db_path)
    core = StudyBuddyCore(db=db)
    yield core

    try:
        if os.path.exists(db_path):
            os.remove(db_path)
    except OSError:
        pass


def test_start_viva_initialization_and_focus_areas(viva_core):
    # Physics Chapter 3 has seeded weak topic 'Rotational Dynamics'
    res = viva_core.start_viva(topic="Rotational Dynamics", num_questions=3, difficulty="intermediate")

    assert res["success"] is True
    assert res["session_id"].startswith("viva_")
    assert res["topic"] == "Rotational Dynamics"
    assert res["difficulty"] == "intermediate"
    assert res["total_questions"] == 3
    assert "Rotational Dynamics" in res["focus_areas"]
    assert "instructions" in res
    assert "Ask ONE open-ended conceptual question" in res["instructions"]
    assert "record_answer" in res["instructions"]
    assert "speech" in res
    assert "Starting a 3-question intermediate viva" in res["speech"]


def test_record_answer_follow_up_rule(viva_core):
    start = viva_core.start_viva(topic="Thermodynamics", num_questions=3, difficulty="intermediate")
    session_id = start["session_id"]

    # Rule: 4 <= score <= 7 with is_follow_up=False -> triggers follow-up
    ans1 = viva_core.record_answer(
        session_id=session_id,
        question="State the second law of thermodynamics.",
        answer="Entropy of an isolated system always increases.",
        score=6.0,
        feedback="Good statement of entropy, but clarify reversibility.",
        missed_points=["reversible processes have constant entropy"],
        is_follow_up=False,
    )

    assert ans1["success"] is True
    assert ans1["next_action"] == "ask_follow_up"
    assert "reversible processes" in ans1["follow_up_hint"]
    assert "is_follow_up=True" in ans1["instructions"]
    assert "elaborate on" in ans1["speech"].lower()

    # Answering the follow-up with is_follow_up=True must NOT trigger a second follow-up
    ans2 = viva_core.record_answer(
        session_id=session_id,
        question="Can you elaborate on reversible processes?",
        answer="In reversible processes, total entropy change is zero.",
        score=7.0,
        feedback="Accurate clarification.",
        missed_points=[],
        is_follow_up=True,
    )

    assert ans2["success"] is True
    # Should move to next question, NOT trigger another follow-up
    assert ans2["next_action"] == "next_question"
    assert ans2["current_question_index"] == 2


def test_record_answer_difficulty_progression(viva_core):
    start = viva_core.start_viva(topic="Electromagnetism", num_questions=3, difficulty="intermediate")
    session_id = start["session_id"]

    # High score (>= 8) bumps intermediate -> advanced
    high_ans = viva_core.record_answer(
        session_id=session_id,
        question="Explain Maxwell's displacement current.",
        answer="Displacement current arises from time-varying electric flux.",
        score=9.0,
        feedback="Masterful explanation.",
        missed_points=[],
        is_follow_up=False,
    )
    assert high_ans["next_difficulty"] == "advanced"

    # Low score (<= 3) drops advanced -> intermediate
    low_ans = viva_core.record_answer(
        session_id=session_id,
        question="Derive the wave equation from Maxwell's equations.",
        answer="I don't know the curls.",
        score=2.0,
        feedback="Need to review curl of B and E.",
        missed_points=["curl equations", "vector identity"],
        is_follow_up=False,
    )
    assert low_ans["next_difficulty"] == "intermediate"


def test_auto_weak_topic_save_and_deduplication(viva_core):
    start = viva_core.start_viva(topic="Quantum Mechanics", num_questions=2, difficulty="intermediate")
    session_id = start["session_id"]

    # Low score (score <= 5) triggers auto-save of weak topic and revision
    ans = viva_core.record_answer(
        session_id=session_id,
        question="Explain the Heisenberg Uncertainty Principle.",
        answer="You cannot measure things at all.",
        score=3.0,
        feedback="Incorrect formulation of conjugate variables.",
        missed_points=["position and momentum commutator"],
        is_follow_up=False,
    )

    assert ans["revision_scheduled"] is True

    # Verify weak topic is saved
    weak_list = viva_core.db.get_weak_topics_for_topic("Quantum Mechanics")
    assert len(weak_list) == 1
    assert weak_list[0]["times_flagged"] == 1
    assert weak_list[0]["severity"] == 3

    # Another failure on the same topic must DEDUPLICATE (increment times_flagged)
    viva_core.save_weak_topic(
        topic="Quantum Mechanics",
        reason="Repeated trouble with wavefunctions",
        severity=3,
        source="viva",
    )
    weak_list2 = viva_core.db.get_weak_topics_for_topic("Quantum Mechanics")
    assert len(weak_list2) == 1
    assert weak_list2[0]["times_flagged"] == 2


def test_viva_session_completion_summary(viva_core):
    start = viva_core.start_viva(topic="Optics", num_questions=2, difficulty="intermediate")
    session_id = start["session_id"]

    # Question 1: Perfect score
    viva_core.record_answer(
        session_id=session_id,
        question="What is Snell's Law?",
        answer="n1 sin theta 1 equals n2 sin theta 2.",
        score=10.0,
        feedback="Perfect definition.",
        missed_points=[],
        is_follow_up=False,
    )

    # Question 2: Decent score to finish the 2-question session
    final_res = viva_core.record_answer(
        session_id=session_id,
        question="What is total internal reflection?",
        answer="When angle of incidence exceeds critical angle in a denser medium.",
        score=8.0,
        feedback="Solid understanding.",
        missed_points=[],
        is_follow_up=False,
    )

    assert final_res["is_finished"] is True
    assert final_res["next_action"] == "finish"
    assert "summary" in final_res
    summary = final_res["summary"]
    assert summary["total_answers"] == 2
    assert summary["average_score"] == 9.0
    assert "Snell's Law" in summary["strongest_question"]
    assert "Viva complete! You averaged 9.0 out of 10" in final_res["speech"]


def test_schedule_revision_tool(viva_core):
    res_today = viva_core.schedule_revision(topic="Fluid Mechanics", days_from_now=0, note="Bernoulli equation")
    assert res_today["success"] is True
    assert res_today["spoken_due"] == "today"

    res_tomorrow = viva_core.schedule_revision(topic="Fluid Mechanics", days_from_now=1, note="Viscosity")
    assert res_tomorrow["spoken_due"] == "tomorrow"

    res_future = viva_core.schedule_revision(topic="Fluid Mechanics", days_from_now=4, note="Navier Stokes")
    assert res_future["spoken_due"] == "in 4 days"


def test_merged_get_weak_topics_and_revision_plan(viva_core):
    # Add a flashcard review failure
    cards = viva_core.db.get_cards_for_quiz("Physics Chapter 3", limit=1)
    viva_core.db.log_review(card_id=cards[0]["id"], quality=1, correct=False, user_answer="bad")

    # Add a viva weak topic
    viva_core.save_weak_topic(topic="Nuclear Fusion", reason="Lawson criterion gap", severity=3, source="viva")

    merged = viva_core.get_weak_topics(limit=3)
    assert len(merged["weak_topics"]) >= 2
    sources = [w.get("source") for w in merged["weak_topics"]]
    assert any("viva" in s for s in sources if s)
    assert "speech" in merged

    # Test unified revision plan
    plan = viva_core.get_revision_plan(days_ahead=3)
    assert "total_due_today" in plan
    assert "upcoming_days" in plan
    assert "upcoming_revisions" in plan
    assert "speech" in plan


def test_bedrock_evaluator_missing_score_error(viva_core):
    start = viva_core.start_viva(topic="Astronomy", num_questions=2)
    session_id = start["session_id"]

    # When Bedrock is not configured and score is omitted, return a friendly error
    with patch.dict(os.environ, {}, clear=True):
        res = viva_core.record_answer(
            session_id=session_id,
            question="What is a red giant?",
            answer="A dying star.",
            score=None,
        )
        assert res["success"] is False
        assert "Score is required" in res["error"]
        assert "Please provide an evaluation score" in res["speech"]


def test_bedrock_evaluator_mocked_converse():
    # Test evaluator with mocked AWS Bedrock Converse response
    mock_response = {
        "output": {
            "message": {
                "content": [
                    {
                        "text": '{"score": 8, "feedback": "Well articulated explanation of orbital decay.", "missed_points": ["tidal forces"]}'
                    }
                ]
            }
        }
    }

    with patch.dict(os.environ, {"BEDROCK_MODEL_ID": "anthropic.claude-3-haiku-20240307-v1:0"}):
        with patch("boto3.client") as mock_boto:
            mock_client = MagicMock()
            mock_client.converse.return_value = mock_response
            mock_boto.return_value = mock_client

            result = evaluate_viva_answer_bedrock(
                question="Why do orbits decay?",
                answer="Atmospheric drag removes kinetic energy.",
                topic="Astrophysics",
                difficulty="intermediate",
            )

            assert result is not None
            assert result["score"] == 8
            assert "orbital decay" in result["feedback"]
            assert result["missed_points"] == ["tidal forces"]
