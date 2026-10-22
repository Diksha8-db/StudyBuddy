"""
Unit tests for SM-2 Spaced Repetition Algorithm.
"""

from datetime import date, timedelta
from studybuddy.sm2 import calculate_sm2


def test_sm2_first_repetition_success():
    ref_date = date(2026, 10, 22)
    # Quality 5 on first repetition (repetitions = 0)
    reps, interval, ease, due_date = calculate_sm2(
        quality=5,
        repetitions=0,
        ease_factor=2.5,
        interval_days=0,
        reference_date=ref_date,
    )

    assert reps == 1
    assert interval == 1
    assert ease >= 2.5  # Ease should increase or remain high
    assert due_date == (ref_date + timedelta(days=1)).isoformat()


def test_sm2_second_repetition_success():
    ref_date = date(2026, 10, 22)
    # Quality 4 on second repetition (repetitions = 1)
    reps, interval, ease, due_date = calculate_sm2(
        quality=4,
        repetitions=1,
        ease_factor=2.6,
        interval_days=1,
        reference_date=ref_date,
    )

    assert reps == 2
    assert interval == 6
    assert due_date == (ref_date + timedelta(days=6)).isoformat()


def test_sm2_subsequent_repetition():
    ref_date = date(2026, 10, 22)
    # Quality 5 on third repetition (repetitions = 2) with ease 2.5 and previous interval 6
    reps, interval, ease, due_date = calculate_sm2(
        quality=5,
        repetitions=2,
        ease_factor=2.5,
        interval_days=6,
        reference_date=ref_date,
    )

    assert reps == 3
    # interval should be round(6 * new_ease)
    assert interval == round(6 * ease)
    assert interval >= 15
    assert due_date == (ref_date + timedelta(days=interval)).isoformat()


def test_sm2_failure_resets_repetition_and_interval():
    ref_date = date(2026, 10, 22)
    # Quality 2 (failure) even after 5 successful repetitions
    reps, interval, ease, due_date = calculate_sm2(
        quality=2,
        repetitions=5,
        ease_factor=2.5,
        interval_days=25,
        reference_date=ref_date,
    )

    assert reps == 0
    assert interval == 1
    assert ease < 2.5  # Ease should decrease after failure
    assert due_date == (ref_date + timedelta(days=1)).isoformat()


def test_sm2_minimum_ease_factor():
    ref_date = date(2026, 10, 22)
    # Even with repeated failures (quality 0), ease factor never drops below 1.3
    ease = 1.35
    for _ in range(5):
        _, _, ease, _ = calculate_sm2(
            quality=0,
            repetitions=0,
            ease_factor=ease,
            interval_days=1,
            reference_date=ref_date,
        )

    assert ease >= 1.3
