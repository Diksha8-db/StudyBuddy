"""
Core Tool implementations for StudyBuddy MCP.

All tools follow voice-first design rules:
1. Short, plain sentences suitable for text-to-speech (TTS).
2. Never include markdown symbols (like asterisks, hashtags, or links) in the 'speech' field.
3. Keep lists capped at 3 items.
4. Return structured JSON with a dedicated 'speech' field alongside raw data.
"""

from typing import Any, Dict, Optional
from studybuddy.db import Database
from studybuddy.grader import grade_answer as evaluate_answer
from studybuddy.sm2 import calculate_sm2


class StudyBuddyCore:
    def __init__(self, db: Optional[Database] = None):
        self.db = db or Database()

    def add_flashcard(
        self,
        deck: str,
        question: str,
        answer: str,
        topic: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Add a new flashcard to a study deck.

        Use this tool when the user wants to remember a concept, definition, formula,
        or fact. Alexa can also call this repeatedly to convert notes into flashcards.

        Args:
            deck: The name of the subject or deck (e.g. 'Physics Chapter 3').
            question: The question or prompt for active recall.
            answer: The correct explanation or answer to be recalled.
            topic: Optional subtopic tag (e.g. 'Newton's Laws', 'Friction').

        Returns:
            Dict containing card_id, status, confirmation, and voice speech text.
        """
        if not deck or not deck.strip():
            return {
                "success": False,
                "error": "Deck name is required.",
                "speech": "Please specify which deck you would like to add this flashcard to.",
            }
        if not question or not question.strip():
            return {
                "success": False,
                "error": "Question is required.",
                "speech": "What question should I put on this flashcard?",
            }
        if not answer or not answer.strip():
            return {
                "success": False,
                "error": "Answer is required.",
                "speech": "What is the answer for this card?",
            }

        card_id = self.db.add_card(deck=deck, question=question, answer=answer, topic=topic)
        topic_clause = f" under {topic}" if topic else ""
        speech = f"Added card to {deck}{topic_clause}. Question: {question.strip()}"

        return {
            "success": True,
            "card_id": card_id,
            "deck": deck.strip(),
            "topic": topic.strip() if topic else None,
            "question": question.strip(),
            "speech": speech,
        }

    def list_decks(self) -> Dict[str, Any]:
        """
        List all available flashcard decks with their total card and due counts.

        Use this tool when the user asks what decks they have or what they can study.

        Returns:
            Dict containing list of decks, counts, and voice speech text.
        """
        decks = self.db.list_decks()
        if not decks:
            return {
                "decks": [],
                "count": 0,
                "speech": "You don't have any flashcard decks yet. You can create one by saying 'Add a card to Physics'.",
            }

        # Cap voice summary at 3 decks for speech
        voice_items = []
        for d in decks[:3]:
            due = d.get("due_cards", 0) or 0
            total = d.get("total_cards", 0)
            name = d.get("deck")
            if due > 0:
                voice_items.append(f"{name} with {due} due out of {total}")
            else:
                voice_items.append(f"{name} with {total} cards")

        if len(decks) == 1:
            speech = f"You have 1 deck: {voice_items[0]}."
        elif len(decks) <= 3:
            speech = f"You have {len(decks)} decks: {', and '.join(voice_items)}."
        else:
            remaining = len(decks) - 3
            speech = f"You have {len(decks)} decks including {', '.join(voice_items[:2])}, and {remaining} more."

        return {
            "decks": decks,
            "count": len(decks),
            "speech": speech,
        }

    def start_quiz(
        self,
        deck: str,
        num_questions: int = 5,
        mode: str = "mixed",
    ) -> Dict[str, Any]:
        """
        Start an active recall quiz session for a specified deck.

        Use this tool when the user says 'Quiz me on Physics' or 'Practice my weak topics'.
        This returns a session ID and the very first question only. The answer is never returned.

        Args:
            deck: The deck name to quiz on.
            num_questions: Number of questions to ask (default 5, max 15).
            mode: Card selection strategy: 'due' for overdue cards, 'weak' for highest
                  miss rate, or 'mixed' for balanced review.

        Returns:
            Dict containing session_id, card_id, question, index, and voice speech text.
        """
        if not deck or not deck.strip():
            return {
                "success": False,
                "error": "Deck name is required.",
                "speech": "Which deck would you like to quiz on? For example, you can say Physics Chapter 3.",
            }

        clean_mode = mode.lower().strip()
        if clean_mode not in ("due", "weak", "mixed"):
            clean_mode = "mixed"

        limit = max(1, min(15, int(num_questions)))
        cards = self.db.get_cards_for_quiz(deck=deck.strip(), limit=limit, mode=clean_mode)

        if not cards:
            return {
                "success": False,
                "error": f"No cards found for deck '{deck}'.",
                "speech": f"I couldn't find any flashcards in the deck {deck}. Would you like to create one?",
            }

        card_ids = [c["id"] for c in cards]
        session_id = self.db.create_session(deck=deck.strip(), card_ids=card_ids)
        first_card = cards[0]

        speech = (
            f"Starting a {len(cards)} question quiz on {deck}. "
            f"Question 1: {first_card['question']}"
        )

        return {
            "success": True,
            "session_id": session_id,
            "deck": deck.strip(),
            "total_questions": len(cards),
            "current_index": 1,
            "card_id": first_card["id"],
            "question": first_card["question"],
            "topic": first_card.get("topic"),
            "speech": speech,
        }

    def grade_answer(
        self,
        session_id: str,
        card_id: int,
        user_answer: str,
        quality: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Grade a user's spoken or typed answer to a quiz question.

        Use this tool when the user responds to a quiz question. It evaluates the answer,
        applies the SM-2 spaced repetition update to schedule future review, logs the attempt,
        and returns the verdict, correct answer, and either the next question or final quiz score.

        Args:
            session_id: The active quiz session ID.
            card_id: ID of the card being answered.
            user_answer: The transcribed answer spoken by the user.
            quality: Optional 0-5 rating if pre-judged by Alexa or an LLM.

        Returns:
            Dict containing verdict, score, correct_answer, next question or completion summary.
        """
        session = self.db.get_session(session_id)
        if not session:
            return {
                "success": False,
                "error": f"Session '{session_id}' not found.",
                "speech": "I couldn't find an active quiz session. Would you like to start a new quiz?",
            }

        card = self.db.get_card(card_id)
        if not card:
            return {
                "success": False,
                "error": f"Card ID {card_id} not found.",
                "speech": "I couldn't locate that flashcard in the database.",
            }

        # 1. Grade the answer
        grade = evaluate_answer(
            expected_answer=card["answer"],
            user_answer=user_answer,
            quality=quality,
        )

        # 2. Update SM-2 schedule
        new_reps, new_interval, new_ease, new_due = calculate_sm2(
            quality=grade.quality,
            repetitions=card.get("repetitions", 0) or 0,
            ease_factor=card.get("ease_factor", 2.5) or 2.5,
            interval_days=card.get("interval_days", 0) or 0,
        )
        self.db.update_card_sm2(
            card_id=card_id,
            repetitions=new_reps,
            interval_days=new_interval,
            ease_factor=new_ease,
            due_date=new_due,
        )

        # 3. Log the review
        self.db.log_review(
            card_id=card_id,
            quality=grade.quality,
            correct=grade.is_correct,
            user_answer=user_answer,
        )

        # 4. Advance the session
        session_progress = self.db.advance_session(session_id, is_correct=grade.is_correct)
        is_finished = session_progress["is_finished"]
        current_index = session_progress["current_index"]
        card_ids = session_progress["card_ids"]
        correct_count = session_progress["correct_count"]
        total_questions = session_progress["total_questions"]

        # Voice feedback generation
        if grade.is_correct:
            if new_interval == 1:
                interval_msg = "You'll see this again tomorrow."
            else:
                interval_msg = f"You'll see this again in {new_interval} days."
            verdict_speech = f"{grade.feedback} {interval_msg}"
        else:
            verdict_speech = f"Not quite. The correct answer is: {card['answer']}. I'll bring this card back tomorrow."

        if not is_finished:
            next_card_id = card_ids[current_index]
            next_card = self.db.get_card(next_card_id)
            next_q_num = current_index + 1
            speech = f"{verdict_speech} Question {next_q_num}: {next_card['question']}"

            return {
                "success": True,
                "session_id": session_id,
                "verdict": grade.verdict,
                "is_correct": grade.is_correct,
                "score": grade.score,
                "quality": grade.quality,
                "correct_answer": card["answer"],
                "is_finished": False,
                "next_question_index": next_q_num,
                "total_questions": total_questions,
                "next_card_id": next_card_id,
                "next_question": next_card["question"],
                "speech": speech,
            }
        else:
            summary_speech = f"{verdict_speech} Quiz complete! You got {correct_count} out of {total_questions} questions correct."
            return {
                "success": True,
                "session_id": session_id,
                "verdict": grade.verdict,
                "is_correct": grade.is_correct,
                "score": grade.score,
                "quality": grade.quality,
                "correct_answer": card["answer"],
                "is_finished": True,
                "correct_count": correct_count,
                "total_questions": total_questions,
                "speech": summary_speech,
            }

    def get_weak_topics(
        self,
        deck: Optional[str] = None,
        limit: int = 3,
    ) -> Dict[str, Any]:
        """
        Identify weak study topics based on past review miss rates.

        Use this tool when the user asks 'What are my weak spots?', 'What should I study?',
        or 'Where am I struggling?'.

        Args:
            deck: Optional deck filter (e.g. 'Physics Chapter 3').
            limit: Maximum number of weak topics to return (default 3).

        Returns:
            Dict containing weak topics ranked by miss rate, and voice speech text.
        """
        safe_limit = max(1, min(5, int(limit)))
        topics = self.db.get_weak_topics(deck=deck, limit=safe_limit)

        if not topics:
            deck_clause = f" in {deck}" if deck else ""
            return {
                "deck": deck,
                "weak_topics": [],
                "speech": f"Great news! You don't have any weak topics identified yet{deck_clause}. Keep quizzing to build your learning profile.",
            }

        topic_phrases = []
        for t in topics[:3]:
            rate_pct = int(round(t["miss_rate"] * 100))
            topic_phrases.append(f"{t['topic']} with a {rate_pct} percent miss rate")

        if len(topics) == 1:
            speech = f"Your weakest topic is {topic_phrases[0]}. Would you like to practice questions on it?"
        else:
            speech = f"Your weakest topics are {', and '.join(topic_phrases)}. Would you like to drill those?"

        return {
            "deck": deck,
            "weak_topics": topics,
            "speech": speech,
        }

    def schedule_review(
        self,
        deck: Optional[str] = None,
        days_ahead: int = 3,
    ) -> Dict[str, Any]:
        """
        Check cards due for spaced repetition review today and in upcoming days.

        Use this tool when the user asks 'Do I have any reviews today?' or 'When should I study next?'.

        Args:
            deck: Optional deck name to filter by.
            days_ahead: Number of future days to check (default 3).

        Returns:
            Dict containing due today count, upcoming schedule, and voice speech text.
        """
        safe_days = max(1, min(7, int(days_ahead)))
        sched = self.db.schedule_review(deck=deck, days_ahead=safe_days)

        due_today = sched["due_today"]
        upcoming_total = sum(d["due_count"] for d in sched["upcoming_days"])

        deck_clause = f" for {deck}" if deck else ""
        if due_today == 0 and upcoming_total == 0:
            speech = f"You are all caught up{deck_clause}! No cards are due today or in the next {safe_days} days."
        elif due_today > 0 and upcoming_total == 0:
            card_word = "card" if due_today == 1 else "cards"
            speech = f"You have {due_today} {card_word} due for review today{deck_clause}. Would you like to quiz now?"
        elif due_today == 0:
            speech = f"No cards are due today{deck_clause}, but you have {upcoming_total} upcoming over the next {safe_days} days."
        else:
            speech = f"You have {due_today} cards due today{deck_clause}, and {upcoming_total} more scheduled over the next {safe_days} days."

        return {
            "deck": deck,
            "due_today": due_today,
            "upcoming_days": sched["upcoming_days"],
            "total_due_in_window": sched["total_due_in_window"],
            "speech": speech,
        }
