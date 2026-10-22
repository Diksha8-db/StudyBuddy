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
        topics = self.db.get_merged_weak_topics(deck=deck, limit=safe_limit)

        if not topics:
            deck_clause = f" in {deck}" if deck else ""
            return {
                "deck": deck,
                "weak_topics": [],
                "speech": f"Great news! You don't have any weak topics identified yet{deck_clause}. Keep practicing to build your profile.",
            }

        topic_phrases = []
        for t in topics[:3]:
            source_tag = f" from {t.get('source', 'reviews')}"
            if t.get("miss_rate") is not None:
                rate_pct = int(round(t["miss_rate"] * 100))
                topic_phrases.append(f"{t['topic']} with a {rate_pct} percent miss rate")
            else:
                topic_phrases.append(f"{t['topic']}{source_tag}")

        if len(topics) == 1:
            speech = f"Your weakest topic is {topic_phrases[0]}. Would you like to practice questions on it?"
        else:
            speech = f"Your weakest topics are {', and '.join(topic_phrases)}. Would you like to drill those?"

        return {
            "deck": deck,
            "weak_topics": topics,
            "speech": speech,
        }

    def get_revision_plan(
        self,
        deck: Optional[str] = None,
        days_ahead: int = 3,
    ) -> Dict[str, Any]:
        """
        Get unified revision plan combining due flashcards and scheduled viva revisions.

        Use this tool when the user asks 'What is my revision plan?' or 'What do I need to study today?'.

        Args:
            deck: Optional deck filter.
            days_ahead: Days into the future to forecast (default 3).

        Returns:
            Dict containing flashcards due, revisions due, upcoming schedule, and voice speech.
        """
        safe_days = max(1, min(7, int(days_ahead)))
        plan = self.db.get_combined_revision_plan(deck=deck, days_ahead=safe_days)

        fc_due = plan["flashcards_due_today"]
        rev_due = plan["revisions_due_today"]
        total_due = plan["total_due_today"]
        upcoming_fc = sum(d["due_count"] for d in plan["upcoming_flashcards"])
        upcoming_rev = sum(d["count"] for d in plan["upcoming_revisions"])
        total_upcoming = upcoming_fc + upcoming_rev

        deck_clause = f" for {deck}" if deck else ""
        if total_due == 0 and total_upcoming == 0:
            speech = f"You are completely caught up{deck_clause}! No flashcards or revisions are due today or in the next {safe_days} days."
        elif total_due > 0 and total_upcoming == 0:
            items_desc = []
            if fc_due > 0:
                items_desc.append(f"{fc_due} flashcard{'s' if fc_due != 1 else ''}")
            if rev_due > 0:
                items_desc.append(f"{rev_due} topic revision{'s' if rev_due != 1 else ''}")
            speech = f"You have {' and '.join(items_desc)} due today{deck_clause}. Ready to start?"
        elif total_due == 0:
            speech = f"Nothing is due today{deck_clause}, but you have {total_upcoming} items coming up over the next {safe_days} days."
        else:
            speech = f"You have {fc_due} flashcards and {rev_due} revisions due today{deck_clause}, plus {total_upcoming} scheduled over the next {safe_days} days."

        # Keep backward compatible fields alongside new fields
        return {
            "deck": deck,
            "due_today": fc_due,
            "flashcards_due_today": fc_due,
            "revisions_due_today": rev_due,
            "total_due_today": total_due,
            "upcoming_days": plan["upcoming_flashcards"],
            "upcoming_revisions": plan["upcoming_revisions"],
            "total_due_in_window": total_due + total_upcoming,
            "speech": speech,
        }

    def schedule_review(
        self,
        deck: Optional[str] = None,
        days_ahead: int = 3,
    ) -> Dict[str, Any]:
        """
        Check cards and revisions due today and upcoming. Thin alias for get_revision_plan.

        Use this tool when checking review schedule.
        """
        return self.get_revision_plan(deck=deck, days_ahead=days_ahead)

    # -----------------------------------------------------------------------
    # VivaMate Tools
    # -----------------------------------------------------------------------

    def start_viva(
        self,
        topic: str,
        num_questions: int = 5,
        difficulty: str = "intermediate",
    ) -> Dict[str, Any]:
        """
        Start an oral viva practice session on a specific topic.

        WHEN TO USE: Call this tool when the user says 'Practice viva on Physics',
        'Exam viva on Newton's Laws', or 'Test me on concepts'.
        The calling agent (Alexa+) generates open-ended conceptual questions and scores them.
        The server manages session state, focus areas, difficulty progression, and memory.

        Args:
            topic: The subject or topic of the viva exam (e.g. 'Newtonian Mechanics').
            num_questions: Number of questions for this session (default 5, max 15).
            difficulty: Starting difficulty: 'beginner', 'intermediate', or 'advanced'.

        Returns:
            Dict containing session_id, focus_areas, instructions for the agent, and speech.
        """
        if not topic or not topic.strip():
            return {
                "success": False,
                "error": "Topic is required.",
                "speech": "What topic would you like to practice viva for?",
            }

        clean_diff = difficulty.lower().strip()
        if clean_diff not in ("beginner", "intermediate", "advanced"):
            clean_diff = "intermediate"

        limit_q = max(1, min(15, int(num_questions)))

        # Look up existing weak topics matching this topic to guide the agent
        weak_matches = self.db.get_weak_topics_for_topic(topic.strip())
        focus_areas = [w["topic"] for w in weak_matches[:3]]

        session_id = self.db.create_viva_session(
            topic=topic.strip(),
            difficulty=clean_diff,
            num_questions=limit_q,
        )

        focus_speech = ""
        if focus_areas:
            focus_speech = f" I'll emphasize your past weak areas like {', '.join(focus_areas)}."

        speech = (
            f"Starting a {limit_q}-question {clean_diff} viva on {topic.strip()}.{focus_speech} "
            f"I'm ready for Question 1."
        )

        focus_instruction = (
            f" (focusing especially on {', '.join(focus_areas)})" if focus_areas else ""
        )
        instructions = (
            f"Ask ONE open-ended conceptual question on '{topic.strip()}' at {clean_diff} difficulty"
            f"{focus_instruction}. After the student answers, call record_answer with your score (0-10) and feedback."
        )

        return {
            "success": True,
            "session_id": session_id,
            "topic": topic.strip(),
            "difficulty": clean_diff,
            "total_questions": limit_q,
            "current_question_index": 1,
            "focus_areas": focus_areas,
            "instructions": instructions,
            "speech": speech,
        }

    def record_answer(
        self,
        session_id: str,
        question: str,
        answer: str,
        score: Optional[float] = None,
        feedback: Optional[str] = None,
        missed_points: Optional[list] = None,
        is_follow_up: bool = False,
    ) -> Dict[str, Any]:
        """
        Record and evaluate a student's answer in an active viva exam session.

        WHEN TO USE: Call this tool immediately after the student speaks their answer
        to a viva question. The agent provides a score (0-10) and feedback. If score is
        omitted and BEDROCK_MODEL_ID is set, the server evaluates via AWS Bedrock.
        Automatically updates difficulty, triggers follow-up questions when needed,
        saves weak topics, and schedules revisions.

        Args:
            session_id: The active viva session ID from start_viva.
            question: The question that was asked to the student.
            answer: The student's spoken answer.
            score: Score from 0 to 10 (0=fail, 10=flawless). Required unless Bedrock is configured.
            feedback: Constructive 1-2 sentence spoken feedback for the student.
            missed_points: Optional list of key concepts or points the student missed.
            is_follow_up: True if this answer was for a follow-up probe.

        Returns:
            Dict containing next_action, next_difficulty, instructions for agent, and speech.
        """
        session = self.db.get_viva_session(session_id)
        if not session:
            return {
                "success": False,
                "error": f"Viva session '{session_id}' not found.",
                "speech": "I couldn't find an active viva session. Would you like to start a new one?",
            }

        # Check Bedrock evaluation fallback if score is missing
        if score is None:
            from studybuddy.evaluator import evaluate_viva_answer_bedrock
            evaluated = evaluate_viva_answer_bedrock(
                question=question,
                answer=answer,
                topic=session["topic"],
                difficulty=session["difficulty"],
            )
            if evaluated:
                score = evaluated["score"]
                feedback = feedback or evaluated["feedback"]
                missed_points = missed_points or evaluated["missed_points"]
            else:
                return {
                    "success": False,
                    "error": "Score is required. Please provide a score from 0 to 10.",
                    "speech": "Please provide an evaluation score from 0 to 10 for the student's answer.",
                }

        # Validate score range
        try:
            numeric_score = float(score)
            if numeric_score < 0.0 or numeric_score > 10.0:
                raise ValueError("Score out of range")
        except (ValueError, TypeError):
            return {
                "success": False,
                "error": "Score must be a number between 0 and 10.",
                "speech": "Please provide a valid score between 0 and 10.",
            }

        clean_missed = [str(p) for p in (missed_points or [])]
        clean_feedback = (feedback or "Good attempt.").strip()

        # 1. Persist answer to database
        self.db.add_viva_answer(
            session_id=session_id,
            question=question,
            answer=answer,
            score=numeric_score,
            feedback=clean_feedback,
            missed_points=clean_missed,
            is_follow_up=is_follow_up,
        )

        # 2. Auto-save weak topic & schedule revision if score <= 5
        revision_created = False
        if numeric_score <= 5.0:
            severity = 3 if numeric_score <= 3.0 else 2
            reason = clean_feedback or f"Low viva score {numeric_score}/10"
            self.db.save_or_update_weak_topic(
                topic=session["topic"],
                reason=reason,
                severity=severity,
                source="viva",
            )
            from datetime import date, timedelta
            tomorrow_str = (date.today() + timedelta(days=1)).isoformat()
            self.db.add_revision(
                topic=session["topic"],
                due_date=tomorrow_str,
                note=f"Viva score {numeric_score}/10: {clean_feedback}",
            )
            revision_created = True

        # 3. Dynamic difficulty progression
        levels = ["beginner", "intermediate", "advanced"]
        current_diff = session.get("difficulty", "intermediate").lower()
        if current_diff not in levels:
            current_diff = "intermediate"
        curr_idx = levels.index(current_diff)

        if numeric_score >= 8.0:
            next_idx = min(len(levels) - 1, curr_idx + 1)
        elif numeric_score <= 3.0:
            next_idx = max(0, curr_idx - 1)
        else:
            next_idx = curr_idx
        next_difficulty = levels[next_idx]

        # 4. Update session index and totals
        # A follow-up does not advance the primary question counter
        new_index = session["current_index"] + (0 if is_follow_up else 1)
        new_total_score = session["total_score"] + numeric_score

        # Follow-up rule: if 4 <= score <= 7 and is_follow_up is False -> ask ONE follow-up
        should_follow_up = (4.0 <= numeric_score <= 7.0) and (not is_follow_up)

        if should_follow_up:
            hint = clean_missed[0] if clean_missed else "the underlying conceptual principle"
            self.db.update_viva_session(
                session_id=session_id,
                current_index=new_index,
                total_score=new_total_score,
                difficulty=next_difficulty,
            )
            instructions = (
                f"Ask ONE probing follow-up question digging deeper into '{hint}'. "
                f"When recording the student's answer, set is_follow_up=True."
            )
            speech = f"{clean_feedback} Let's explore that a bit deeper. Can you elaborate on {hint}?"

            return {
                "success": True,
                "session_id": session_id,
                "score": numeric_score,
                "feedback": clean_feedback,
                "next_action": "ask_follow_up",
                "next_difficulty": next_difficulty,
                "follow_up_hint": hint,
                "revision_scheduled": revision_created,
                "instructions": instructions,
                "speech": speech,
            }

        # Check if session is finished
        is_finished = new_index >= session["num_questions"]
        from datetime import datetime
        finished_at = datetime.now().isoformat() if is_finished else None

        self.db.update_viva_session(
            session_id=session_id,
            current_index=new_index,
            total_score=new_total_score,
            finished_at=finished_at,
            difficulty=next_difficulty,
        )

        if not is_finished:
            instructions = (
                f"Ask Question {new_index + 1} of {session['num_questions']} on '{session['topic']}' "
                f"at {next_difficulty} difficulty. Then call record_answer."
            )
            speech = f"{clean_feedback} Moving to Question {new_index + 1}."

            return {
                "success": True,
                "session_id": session_id,
                "score": numeric_score,
                "feedback": clean_feedback,
                "next_action": "next_question",
                "next_difficulty": next_difficulty,
                "current_question_index": new_index + 1,
                "total_questions": session["num_questions"],
                "revision_scheduled": revision_created,
                "instructions": instructions,
                "speech": speech,
            }
        else:
            # Session Complete - build summary
            answers = self.db.get_viva_answers(session_id)
            total_answers = len(answers)
            avg_score = round(sum(a["score"] for a in answers) / max(1, total_answers), 1)

            sorted_answers = sorted(answers, key=lambda a: a["score"])
            weakest_q = sorted_answers[0]["question"] if sorted_answers else "N/A"
            strongest_q = sorted_answers[-1]["question"] if sorted_answers else "N/A"

            summary = {
                "total_answers": total_answers,
                "average_score": avg_score,
                "strongest_question": strongest_q,
                "weakest_question": weakest_q,
                "revisions_created": 1 if revision_created else 0,
            }

            instructions = (
                "The viva session is complete. Share the final summary score with the student and congratulate them."
            )
            speech = (
                f"{clean_feedback} Viva complete! You averaged {avg_score} out of 10 across {total_answers} questions. "
                f"I've added your weaker areas to your spaced revision schedule."
            )

            return {
                "success": True,
                "session_id": session_id,
                "score": numeric_score,
                "feedback": clean_feedback,
                "next_action": "finish",
                "is_finished": True,
                "summary": summary,
                "instructions": instructions,
                "speech": speech,
            }

    def save_weak_topic(
        self,
        topic: str,
        reason: str,
        severity: int = 2,
        source: str = "viva",
    ) -> Dict[str, Any]:
        """
        Manually record or flag a weak topic in shared memory.

        WHEN TO USE: Call this tool when the student says 'I always forget Rotational Dynamics'
        or the agent identifies a conceptual weak point outside of an active quiz.

        Args:
            topic: The concept or subject (e.g. 'Thermodynamics Second Law').
            reason: Why this topic is flagged as weak.
            severity: Urgency from 1 (minor) to 3 (critical).
            source: Origin of flag (default 'viva').

        Returns:
            Dict containing topic, times_flagged, confirmation, and voice speech text.
        """
        if not topic or not topic.strip():
            return {
                "success": False,
                "error": "Topic is required.",
                "speech": "What topic would you like to flag as a weak area?",
            }

        res = self.db.save_or_update_weak_topic(
            topic=topic.strip(),
            reason=reason.strip() if reason else "Manually flagged",
            severity=severity,
            source=source,
        )

        speech = f"Flagged {topic.strip()} as a priority weak topic. I'll include it in your upcoming review plans."
        return {
            "success": True,
            "topic": res["topic"],
            "severity": res["severity"],
            "times_flagged": res["times_flagged"],
            "source": res["source"],
            "speech": speech,
        }

    def schedule_revision(
        self,
        topic: str,
        days_from_now: int = 1,
        note: str = "",
    ) -> Dict[str, Any]:
        """
        Schedule a dedicated revision session for a topic.

        WHEN TO USE: Call this tool when the student or agent wants to schedule a review
        for a specific concept in the near future.

        Args:
            topic: The topic to revise.
            days_from_now: Days until review is due (0=today, 1=tomorrow, etc.).
            note: Optional study hint or note.

        Returns:
            Dict containing topic, due_date, spoken_due, and voice speech text.
        """
        if not topic or not topic.strip():
            return {
                "success": False,
                "error": "Topic is required.",
                "speech": "What topic would you like to schedule for revision?",
            }

        from datetime import date, timedelta
        target_days = max(0, int(days_from_now))
        due_date = (date.today() + timedelta(days=target_days)).isoformat()

        rev_id = self.db.add_revision(
            topic=topic.strip(),
            due_date=due_date,
            note=note.strip() if note else "Scheduled revision",
        )

        if target_days == 0:
            spoken_due = "today"
        elif target_days == 1:
            spoken_due = "tomorrow"
        else:
            spoken_due = f"in {target_days} days"

        speech = f"Scheduled a revision session for {topic.strip()} {spoken_due}."

        return {
            "success": True,
            "revision_id": rev_id,
            "topic": topic.strip(),
            "due_date": due_date,
            "spoken_due": spoken_due,
            "speech": speech,
        }
