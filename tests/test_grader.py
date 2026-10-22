"""
Unit tests for answer grading engine (rapidfuzz & quality ratings).
"""

from studybuddy.grader import grade_answer


def test_grader_exact_match():
    expected = "Force equals mass times acceleration."
    user = "Force equals mass times acceleration."
    result = grade_answer(expected, user)

    assert result.is_correct is True
    assert result.verdict == "correct"
    assert result.quality == 5
    assert result.score >= 95.0


def test_grader_spoken_variation():
    expected = "Force equals mass times acceleration."
    user = "Well force is equal to mass times acceleration"
    result = grade_answer(expected, user)

    assert result.is_correct is True
    assert result.verdict == "correct"
    assert result.quality == 5
    assert result.score >= 85.0


def test_grader_partial_match():
    expected = "Momentum equals mass times velocity."
    user = "Momentum is mass and speed"
    result = grade_answer(expected, user)

    # Should register as partial or correct with rapidfuzz token similarity
    assert result.is_correct is True
    assert result.quality >= 3


def test_grader_incorrect():
    expected = "Static friction prevents motion while kinetic friction opposes motion."
    user = "Friction is the speed of light in vacuum."
    result = grade_answer(expected, user)

    assert result.is_correct is False
    assert result.verdict == "incorrect"
    assert result.quality == 2
    assert result.score < 60.0


def test_grader_explicit_quality_override():
    expected = "Force equals mass times acceleration."
    # Even if answer string is empty or weird, explicit quality takes precedence
    result = grade_answer(expected, "I said something weird", quality=4)
    assert result.is_correct is True
    assert result.quality == 4
    assert result.verdict == "correct"

    result_fail = grade_answer(expected, "good looking answer", quality=1)
    assert result_fail.is_correct is False
    assert result_fail.quality == 1
    assert result_fail.verdict == "incorrect"


def test_grader_empty_input():
    expected = "Force equals mass times acceleration."
    result = grade_answer(expected, "")

    assert result.is_correct is False
    assert result.verdict == "incorrect"
    assert result.quality == 0
