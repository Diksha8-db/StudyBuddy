"""
SM-2 Spaced Repetition Algorithm Implementation.

The SuperMemo-2 (SM-2) algorithm calculates the optimal review intervals
for flashcards based on the user's recall quality (0-5 scale).
"""

from datetime import date, timedelta
from typing import Tuple


def calculate_sm2(
    quality: int,
    repetitions: int,
    ease_factor: float = 2.5,
    interval_days: int = 0,
    reference_date: date | None = None,
) -> Tuple[int, int, float, str]:
    """
    Calculate the next repetition count, interval (in days), ease factor, and due date.

    Args:
        quality: User's recall quality (0 to 5).
                 < 3 is a failure/miss.
                 3 = pass with significant difficulty.
                 4 = pass with hesitation.
                 5 = perfect recall.
        repetitions: Current number of consecutive successful repetitions.
        ease_factor: Current easiness factor (minimum 1.3, default 2.5).
        interval_days: Previous interval in days.
        reference_date: Date from which to calculate due date (defaults to today).

    Returns:
        Tuple of (new_repetitions, new_interval_days, new_ease_factor, due_date_str)
    """
    if reference_date is None:
        reference_date = date.today()

    # Clamp quality to 0-5
    q = max(0, min(5, quality))

    # Update ease factor first:
    # ease = ease + 0.1 - (5 - q) * (0.08 + (5 - q) * 0.02)
    # Minimum ease factor is 1.3
    diff = 5 - q
    new_ease = ease_factor + 0.1 - diff * (0.08 + diff * 0.02)
    new_ease = max(1.3, round(new_ease, 2))

    if q < 3:
        # Failure: reset repetition count and schedule review for tomorrow
        new_repetitions = 0
        new_interval = 1
    else:
        # Successful recall
        if repetitions == 0:
            new_interval = 1
        elif repetitions == 1:
            new_interval = 6
        else:
            new_interval = max(1, int(round(interval_days * new_ease)))

        new_repetitions = repetitions + 1

    due_date = reference_date + timedelta(days=new_interval)
    return new_repetitions, new_interval, new_ease, due_date.isoformat()
