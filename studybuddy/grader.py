"""
Answer grading engine for StudyBuddy.

Supports:
1. Direct quality score input (from Alexa+ or an LLM judge) on a 0-5 scale.
2. Intelligent fuzzy matching fallback using rapidfuzz token similarity.
"""

import re
from typing import NamedTuple
from rapidfuzz import fuzz


class GradeResult(NamedTuple):
    quality: int
    verdict: str  # "correct", "partial", or "incorrect"
    is_correct: bool
    score: float
    feedback: str


def normalize_text(text: str) -> str:
    """Normalize spoken or transcribed text for comparison."""
    if not text:
        return ""
    # Lowercase and replace non-alphanumeric (except basic math symbols) with space
    cleaned = text.lower().strip()
    cleaned = re.sub(r"[^\w\s\+\-\*\/=]", " ", cleaned)
    # Collapse multiple whitespaces
    return " ".join(cleaned.split())


def grade_answer(
    expected_answer: str,
    user_answer: str,
    quality: int | None = None,
) -> GradeResult:
    """
    Grade a user's answer against the expected flashcard answer.

    Args:
        expected_answer: The canonical flashcard answer.
        user_answer: The user's spoken or typed answer.
        quality: Optional direct quality score (0-5). If provided, this overrides
                 fuzzy matching.

    Returns:
        GradeResult with quality (0-5), verdict, is_correct, score (0-100), and feedback.
    """
    if quality is not None:
        q = max(0, min(5, int(quality)))
        if q >= 4:
            verdict = "correct"
            is_correct = True
            score = 100.0 if q == 5 else 85.0
            feedback = "Spot on!" if q == 5 else "Good answer."
        elif q == 3:
            verdict = "partial"
            is_correct = True
            score = 70.0
            feedback = "Partially correct."
        else:
            verdict = "incorrect"
            is_correct = False
            score = 30.0 if q == 2 else 0.0
            feedback = "Not quite right."

        return GradeResult(
            quality=q,
            verdict=verdict,
            is_correct=is_correct,
            score=score,
            feedback=feedback,
        )

    # Fuzzy matching fallback using rapidfuzz
    norm_expected = normalize_text(expected_answer)
    norm_user = normalize_text(user_answer)

    if not norm_user:
        return GradeResult(
            quality=0,
            verdict="incorrect",
            is_correct=False,
            score=0.0,
            feedback="No answer provided.",
        )

    # Use combination of token set ratio and partial ratio for spoken recall tolerance
    token_set = fuzz.token_set_ratio(norm_user, norm_expected)
    token_sort = fuzz.token_sort_ratio(norm_user, norm_expected)
    basic_ratio = fuzz.ratio(norm_user, norm_expected)

    # Spoken answers benefit from token_set_ratio to handle extra filler words
    score = max(token_set, 0.7 * token_sort + 0.3 * basic_ratio)

    if score >= 85.0:
        return GradeResult(
            quality=5,
            verdict="correct",
            is_correct=True,
            score=round(score, 1),
            feedback="Correct!",
        )
    elif score >= 60.0:
        return GradeResult(
            quality=3,
            verdict="partial",
            is_correct=True,
            score=round(score, 1),
            feedback="Partially correct.",
        )
    else:
        return GradeResult(
            quality=2,
            verdict="incorrect",
            is_correct=False,
            score=round(score, 1),
            feedback="Incorrect.",
        )
