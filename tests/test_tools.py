"""
End-to-end unit tests for all 6 StudyBuddy MCP tools.
"""

import os
import tempfile
import pytest
from studybuddy.db import Database
from studybuddy.tools import StudyBuddyCore


@pytest.fixture
def test_core():
    # Use temporary file database for clean isolation
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    db = Database(db_path=db_path)
    core = StudyBuddyCore(db=db)
    yield core

    # Cleanup
    try:
        if os.path.exists(db_path):
            os.remove(db_path)
    except OSError:
        pass


def test_tool_list_decks_seed_data(test_core):
    res = test_core.list_decks()
    assert res["count"] >= 1
    deck_names = [d["deck"] for d in res["decks"]]
    assert "Physics Chapter 3" in deck_names
    assert "speech" in res
    assert "Physics Chapter 3" in res["speech"]


def test_tool_add_flashcard(test_core):
    res = test_core.add_flashcard(
        deck="Chemistry 101",
        question="What is the atomic number of Carbon?",
        answer="6",
        topic="Periodic Table",
    )
    assert res["success"] is True
    assert res["card_id"] is not None
    assert "speech" in res
    assert "Chemistry 101" in res["speech"]

    # Verify deck list now includes Chemistry 101
    decks = test_core.list_decks()
    deck_names = [d["deck"] for d in decks["decks"]]
    assert "Chemistry 101" in deck_names


def test_tool_start_quiz_and_grade_answer_full_flow(test_core):
    # 1. Start a 2-question quiz on Physics Chapter 3
    start = test_core.start_quiz(deck="Physics Chapter 3", num_questions=2, mode="mixed")
    assert start["success"] is True
    session_id = start["session_id"]
    first_card_id = start["card_id"]
    assert start["total_questions"] == 2
    assert "question" in start
    # Ensure answer is NEVER exposed in start_quiz
    assert "answer" not in start
    assert "Question 1:" in start["speech"]

    # 2. Grade question 1 with correct answer
    first_card = test_core.db.get_card(first_card_id)
    grade1 = test_core.grade_answer(
        session_id=session_id,
        card_id=first_card_id,
        user_answer=first_card["answer"],
    )
    assert grade1["success"] is True
    assert grade1["is_correct"] is True
    assert grade1["is_finished"] is False
    assert grade1["next_question_index"] == 2
    assert "next_question" in grade1
    assert "Question 2:" in grade1["speech"]

    # 3. Grade question 2 with incorrect answer to finish quiz
    next_card_id = grade1["next_card_id"]
    grade2 = test_core.grade_answer(
        session_id=session_id,
        card_id=next_card_id,
        user_answer="This is completely incorrect gibberish",
    )
    assert grade2["success"] is True
    assert grade2["is_correct"] is False
    assert grade2["is_finished"] is True
    assert grade2["correct_count"] == 1
    assert grade2["total_questions"] == 2
    assert "Quiz complete! You got 1 out of 2" in grade2["speech"]


def test_tool_get_weak_topics(test_core):
    # Before reviews, weak topics is empty or clean
    res_before = test_core.get_weak_topics(deck="Physics Chapter 3")
    assert "speech" in res_before

    # Log 2 failed reviews on a specific topic
    cards = test_core.db.get_cards_for_quiz("Physics Chapter 3", limit=2)
    c1 = cards[0]
    test_core.db.log_review(card_id=c1["id"], quality=1, correct=False, user_answer="wrong")
    test_core.db.log_review(card_id=c1["id"], quality=2, correct=False, user_answer="wrong again")

    res_after = test_core.get_weak_topics(deck="Physics Chapter 3")
    assert len(res_after["weak_topics"]) >= 1
    top_weak = res_after["weak_topics"][0]
    assert top_weak["topic"] == c1["topic"]
    assert top_weak["miss_rate"] == 1.0
    assert "weakest topic" in res_after["speech"].lower()


def test_tool_schedule_review(test_core):
    res = test_core.schedule_review(days_ahead=3)
    assert "due_today" in res
    assert "upcoming_days" in res
    assert len(res["upcoming_days"]) == 3
    assert "speech" in res
