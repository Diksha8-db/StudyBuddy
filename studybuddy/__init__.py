"""
StudyBuddy: Your hands-free, voice-first study partner that remembers what you forget.
"""

from studybuddy.db import Database
from studybuddy.grader import grade_answer
from studybuddy.sm2 import calculate_sm2
from studybuddy.tools import StudyBuddyCore
from studybuddy.evaluator import evaluate_viva_answer_bedrock, is_bedrock_enabled

__all__ = [
    "Database",
    "StudyBuddyCore",
    "calculate_sm2",
    "grade_answer",
    "evaluate_viva_answer_bedrock",
    "is_bedrock_enabled",
]
