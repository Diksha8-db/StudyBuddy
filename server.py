"""
StudyBuddy MCP Server - Voice-First Spaced Repetition for Alexa+.

Complies with the MCP specification (Streamable HTTP transport) at /mcp
and provides a /health endpoint alongside an interactive voice simulator at /simulator.
"""

import json
import os
import re
import sys
import time
from typing import Any, Dict, Optional

import uvicorn
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

# Support both MCP 2.x and MCP 1.x FastMCP import paths
try:
    from mcp.server.mcpserver import MCPServer as FastMCP
except ImportError:
    from mcp.server.fastmcp import FastMCP  # type: ignore

from studybuddy.db import Database
from studybuddy.tools import StudyBuddyCore

# Initialize core business logic and database
db_path = os.environ.get("STUDYBUDDY_DB_PATH", "studybuddy.db")
db = Database(db_path=db_path)
core = StudyBuddyCore(db=db)

# Initialize MCP Server instance
mcp = FastMCP("studybuddy")


# ---------------------------------------------------------------------------
# MCP Tool Registrations
# ---------------------------------------------------------------------------

@mcp.tool()
def add_flashcard(
    deck: str,
    question: str,
    answer: str,
    topic: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Add a new flashcard to a study deck.

    Use this tool when the user wants to memorize a fact, formula, definition,
    or concept. Alexa can also call this repeatedly to convert user notes into flashcards.
    Returns a short plain-text 'speech' field suitable for text-to-speech.

    Args:
        deck: The name of the subject or deck (e.g. 'Physics Chapter 3').
        question: The prompt or question to be recalled.
        answer: The canonical correct answer.
        topic: Optional subtopic tag (e.g. "Newton's Laws", "Friction").
    """
    return core.add_flashcard(deck=deck, question=question, answer=answer, topic=topic)


@mcp.tool()
def list_decks() -> Dict[str, Any]:
    """
    List all available flashcard decks with total card counts and due cards.

    Use this tool when the user asks what decks they have or what they can study.
    Returns a short plain-text 'speech' field suitable for text-to-speech.
    """
    return core.list_decks()


@mcp.tool()
def start_quiz(
    deck: str,
    num_questions: int = 5,
    mode: str = "mixed",
) -> Dict[str, Any]:
    """
    Start an active recall quiz session for a specified deck.

    Use this tool when the user asks to quiz on a topic. Modes available:
    - 'due': questions overdue according to SM-2 spaced repetition schedule
    - 'weak': questions on topics with highest historical miss rate
    - 'mixed': balanced selection prioritizing due and weak cards

    Returns session_id and the first question only (never reveals the answer).
    Returns a short plain-text 'speech' field suitable for text-to-speech.

    Args:
        deck: Name of the deck to quiz on (e.g. 'Physics Chapter 3').
        num_questions: Number of questions to ask (default 5).
        mode: 'due', 'weak', or 'mixed'.
    """
    return core.start_quiz(deck=deck, num_questions=num_questions, mode=mode)


@mcp.tool()
def grade_answer(
    session_id: str,
    card_id: int,
    user_answer: str,
    quality: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Grade a user's answer to a quiz question and advance the quiz session.

    Use this tool when the user answers a quiz question. If quality (0-5) is provided
    (e.g., evaluated by an LLM), it will be used directly. Otherwise, it fuzzy matches
    against the expected answer using rapidfuzz (>=85 correct/q5, 60-84 partial/q3, <60 wrong/q2).
    Updates the SM-2 spaced repetition schedule, logs the review, and returns the verdict,
    correct answer, and next question (or final score summary if the quiz is complete).
    Returns a short plain-text 'speech' field suitable for text-to-speech.

    Args:
        session_id: The active quiz session identifier.
        card_id: The ID of the card being answered.
        user_answer: Spoken or typed response from the student.
        quality: Optional direct score from 0 (complete blackout) to 5 (perfect recall).
    """
    return core.grade_answer(
        session_id=session_id,
        card_id=card_id,
        user_answer=user_answer,
        quality=quality,
    )


@mcp.tool()
def get_weak_topics(
    deck: Optional[str] = None,
    limit: int = 3,
) -> Dict[str, Any]:
    """
    Identify topics ranked by miss rate over past review sessions.

    Use this tool when the user asks what topics they are struggling with or need to review.
    Returns a short plain-text 'speech' field suitable for text-to-speech.

    Args:
        deck: Optional deck filter (e.g. 'Physics Chapter 3').
        limit: Number of weak topics to return (default 3, max 5).
    """
    return core.get_weak_topics(deck=deck, limit=limit)


@mcp.tool()
def schedule_review(
    deck: Optional[str] = None,
    days_ahead: int = 3,
) -> Dict[str, Any]:
    """
    Check the SM-2 spaced repetition schedule for reviews due today and upcoming.

    Use this tool when the user asks when they should study next or what is due.
    Returns a short plain-text 'speech' field suitable for text-to-speech.

    Args:
        deck: Optional deck filter.
        days_ahead: Number of future days to check (default 3).
    """
    return core.schedule_review(deck=deck, days_ahead=days_ahead)


@mcp.tool()
def get_revision_plan(
    deck: Optional[str] = None,
    days_ahead: int = 3,
) -> Dict[str, Any]:
    """
    Get a unified revision plan combining due flashcards and scheduled viva topic revisions.

    Use this tool when the user asks 'What is my revision plan?' or 'What do I need to study today?'.
    Returns due counts and a consolidated voice 'speech' field.

    Args:
        deck: Optional deck filter.
        days_ahead: Days into the future to forecast (default 3).
    """
    return core.get_revision_plan(deck=deck, days_ahead=days_ahead)


@mcp.tool()
def start_viva(
    topic: str,
    num_questions: int = 5,
    difficulty: str = "intermediate",
) -> Dict[str, Any]:
    """
    Start an oral viva practice session on a specific topic.

    WHEN TO USE: Call this tool when the student says 'Practice viva on Physics',
    'Exam viva on Newton's Laws', or 'Test me on concepts'.
    The calling agent (Alexa+) generates open-ended conceptual questions and scores them.
    The server manages session state, focus areas, difficulty progression, and memory.
    Returns clear 'instructions' telling the agent what to ask next, plus a 'speech' field.

    Args:
        topic: The subject or topic of the viva exam (e.g. 'Newtonian Mechanics').
        num_questions: Number of questions for this session (default 5, max 15).
        difficulty: Starting difficulty: 'beginner', 'intermediate', or 'advanced'.
    """
    return core.start_viva(topic=topic, num_questions=num_questions, difficulty=difficulty)


@mcp.tool()
def record_answer(
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
    """
    return core.record_answer(
        session_id=session_id,
        question=question,
        answer=answer,
        score=score,
        feedback=feedback,
        missed_points=missed_points,
        is_follow_up=is_follow_up,
    )


@mcp.tool()
def save_weak_topic(
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
    """
    return core.save_weak_topic(
        topic=topic,
        reason=reason,
        severity=severity,
        source=source,
    )


@mcp.tool()
def schedule_revision(
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
    """
    return core.schedule_revision(
        topic=topic,
        days_from_now=days_from_now,
        note=note,
    )


# ---------------------------------------------------------------------------
# HTTP Endpoints: Health Check & Simulator Backend
# ---------------------------------------------------------------------------

async def health_endpoint(request: Request) -> JSONResponse:
    """Health check endpoint complying with hackathon requirements."""
    decks = core.db.list_decks()
    total_cards = sum(d.get("total_cards", 0) for d in decks)
    return JSONResponse(
        {
            "status": "healthy",
            "service": "studybuddy-mcp",
            "version": "1.1.0",
            "transport": "streamable-http",
            "mcp_endpoint": "/mcp",
            "protocol_spec": "2025-11-25+",
            "decks_count": len(decks),
            "total_cards": total_cards,
            "tools": [
                "add_flashcard",
                "list_decks",
                "start_quiz",
                "grade_answer",
                "get_weak_topics",
                "schedule_review",
                "get_revision_plan",
                "start_viva",
                "record_answer",
                "save_weak_topic",
                "schedule_revision",
            ],
        }
    )


async def root_redirect(request: Request) -> RedirectResponse:
    """Redirect root to /simulator web app."""
    return RedirectResponse(url="/simulator/")


async def simulator_decks(request: Request) -> JSONResponse:
    """Endpoint for simulator UI to list decks quickly."""
    res = core.list_decks()
    return JSONResponse(res)


async def simulator_chat(request: Request) -> JSONResponse:
    """
    Simulator voice-chat handler.

    Receives user utterance, maps it to the appropriate MCP tool call,
    executes the tool via the official MCP call_tool pipeline, and returns
    the spoken feedback alongside live tool-call traces for the inspector.
    """
    try:
        body = await request.json()
    except Exception:
        body = {}

    utterance = body.get("message", "").strip()
    session_id = body.get("session_id")
    current_card_id = body.get("card_id")

    tool_name = None
    tool_args: Dict[str, Any] = {}
    lower_u = utterance.lower()

    # Conversational intent router & state machine
    if session_id and str(session_id).startswith("viva_"):
        # Active viva exam session: student is answering a viva prompt
        current_question = body.get("question") or "Explain the core physical principles."
        is_follow_up = bool(body.get("is_follow_up", False))

        # Check if caller supplied score, or evaluate
        score = body.get("score")
        feedback = body.get("feedback")
        missed_points = body.get("missed_points")

        # In the web simulator, if no external judge/Bedrock is set, provide smart scoring
        if score is None and not os.environ.get("BEDROCK_MODEL_ID"):
            word_count = len(utterance.split())
            if word_count >= 8:
                score = 8.5
                feedback = "Great depth and clear conceptual terminology."
                missed_points = []
            elif word_count >= 4:
                score = 6.0
                feedback = "Good foundation, but you left out the mathematical relationship."
                missed_points = ["exact formula derivation and boundary conditions"]
            else:
                score = 3.0
                feedback = "Too brief to demonstrate full conceptual mastery."
                missed_points = ["fundamental definitions and physical examples"]

        tool_name = "record_answer"
        tool_args = {
            "session_id": session_id,
            "question": current_question,
            "answer": utterance,
            "score": score,
            "feedback": feedback,
            "missed_points": missed_points or [],
            "is_follow_up": is_follow_up,
        }

    elif session_id and current_card_id:
        # Active quiz session: student is answering the current question
        tool_name = "grade_answer"
        tool_args = {
            "session_id": session_id,
            "card_id": int(current_card_id),
            "user_answer": utterance,
        }
    elif any(kw in lower_u for kw in ["viva", "oral exam", "interview me"]):
        topic = "Newtonian Mechanics"
        for candidate in ["Physics Chapter 3", "Newtonian Mechanics", "Thermodynamics", "Electromagnetism"]:
            if candidate.lower() in lower_u:
                topic = candidate
                break

        diff = "intermediate"
        if "advanced" in lower_u or "hard" in lower_u:
            diff = "advanced"
        elif "beginner" in lower_u or "easy" in lower_u:
            diff = "beginner"

        tool_name = "start_viva"
        tool_args = {"topic": topic, "num_questions": 3, "difficulty": diff}

    elif any(kw in lower_u for kw in ["quiz", "test", "drill", "practice"]):
        # Match deck name or fallback to "Physics Chapter 3"
        decks = core.db.list_decks()
        matched_deck = "Physics Chapter 3"
        for d in decks:
            if d["deck"].lower() in lower_u:
                matched_deck = d["deck"]
                break

        mode = "mixed"
        if "weak" in lower_u or "struggl" in lower_u:
            mode = "weak"
        elif "due" in lower_u or "overdue" in lower_u:
            mode = "due"

        num_q = 5
        match_num = re.search(r"(\d+)\s*questions?", lower_u)
        if match_num:
            num_q = int(match_num.group(1))

        tool_name = "start_quiz"
        tool_args = {"deck": matched_deck, "num_questions": num_q, "mode": mode}

    elif any(kw in lower_u for kw in ["revision plan", "my plan", "what to study"]):
        tool_name = "get_revision_plan"
        tool_args = {"days_ahead": 3}

    elif any(kw in lower_u for kw in ["weak", "struggl", "miss rate", "hard for me"]):
        tool_name = "get_weak_topics"
        tool_args = {"limit": 3}

    elif any(kw in lower_u for kw in ["schedule", "due", "upcoming", "review next", "when should i"]):
        tool_name = "schedule_review"
        tool_args = {"days_ahead": 3}

    elif any(kw in lower_u for kw in ["deck", "what do i have", "my decks", "list"]):
        tool_name = "list_decks"
        tool_args = {}

    elif "add card" in lower_u or "add flashcard" in lower_u or "new card" in lower_u:
        parts = re.split(r"[:\?]\s*", utterance, maxsplit=2)
        question = parts[1].strip() if len(parts) > 1 else "What is Ohm's Law?"
        answer = parts[2].strip() if len(parts) > 2 else "Voltage equals current times resistance."
        tool_name = "add_flashcard"
        tool_args = {
            "deck": "Physics Chapter 3",
            "question": question,
            "answer": answer,
            "topic": "Electricity",
        }

    else:
        # Fallback to listing decks with helpful prompt
        tool_name = "list_decks"
        tool_args = {}

    # Execute through MCP tool pipeline and record latency for the inspector
    t0 = time.perf_counter()
    mcp_result = await mcp.call_tool(tool_name, tool_args)
    latency_ms = round((time.perf_counter() - t0) * 1000, 1)

    # Extract parsed result
    parsed_data: Dict[str, Any] = {}
    speech = "I didn't quite catch that. Would you like to quiz on Physics Chapter 3?"

    for content_item in mcp_result.content:
        if hasattr(content_item, "text"):
            try:
                parsed_data = json.loads(content_item.text)
                if "speech" in parsed_data:
                    speech = parsed_data["speech"]
            except Exception:
                speech = content_item.text

    # Extract or update session state for the client
    updated_session = None
    if tool_name == "start_quiz" and parsed_data.get("success"):
        updated_session = {
            "type": "quiz",
            "session_id": parsed_data["session_id"],
            "card_id": parsed_data["card_id"],
            "total_questions": parsed_data.get("total_questions", 5),
            "current_index": parsed_data.get("current_index", 1),
            "question": parsed_data.get("question"),
        }
    elif tool_name == "grade_answer" and parsed_data.get("success"):
        if not parsed_data.get("is_finished"):
            updated_session = {
                "type": "quiz",
                "session_id": session_id,
                "card_id": parsed_data.get("next_card_id"),
                "total_questions": parsed_data.get("total_questions", 5),
                "current_index": parsed_data.get("next_question_index", 1),
                "question": parsed_data.get("next_question"),
            }
        else:
            updated_session = None  # Quiz complete
    elif tool_name == "start_viva" and parsed_data.get("success"):
        viva_topic = parsed_data.get("topic", "Physics")
        init_q = f"To begin your {parsed_data.get('difficulty')} viva on {viva_topic}: explain the foundational physical laws and their practical significance."
        updated_session = {
            "type": "viva",
            "session_id": parsed_data["session_id"],
            "topic": viva_topic,
            "difficulty": parsed_data.get("difficulty", "intermediate"),
            "total_questions": parsed_data.get("total_questions", 3),
            "current_index": 1,
            "question": init_q,
            "is_follow_up": False,
        }
    elif tool_name == "record_answer" and parsed_data.get("success"):
        if not parsed_data.get("is_finished"):
            if parsed_data.get("next_action") == "ask_follow_up":
                follow_up_hint = parsed_data.get("follow_up_hint", "this concept")
                f_q = f"Follow-up: Can you elaborate more deeply on {follow_up_hint}?"
                updated_session = {
                    "type": "viva",
                    "session_id": session_id,
                    "topic": body.get("topic", "Physics"),
                    "difficulty": parsed_data.get("next_difficulty", "intermediate"),
                    "total_questions": body.get("total_questions", 3),
                    "current_index": body.get("current_index", 1),
                    "question": f_q,
                    "is_follow_up": True,
                }
            else:
                q_idx = parsed_data.get("current_question_index", 2)
                tot_q = parsed_data.get("total_questions", 3)
                next_d = parsed_data.get("next_difficulty", "intermediate")
                next_q = f"Question {q_idx}: Analyze the dynamic equilibrium and energy conservation principles at {next_d} level."
                updated_session = {
                    "type": "viva",
                    "session_id": session_id,
                    "topic": body.get("topic", "Physics"),
                    "difficulty": next_d,
                    "total_questions": tot_q,
                    "current_index": q_idx,
                    "question": next_q,
                    "is_follow_up": False,
                }
        else:
            updated_session = None  # Viva complete

    return JSONResponse(
        {
            "reply": speech,
            "speech": speech,
            "active_session": updated_session,
            "tool_call": {
                "name": tool_name,
                "arguments": tool_args,
                "result": parsed_data,
                "latency_ms": latency_ms,
            },
        }
    )


# ---------------------------------------------------------------------------
# Starlette Application Construction
# ---------------------------------------------------------------------------

def create_app() -> Starlette:
    """Build the production Starlette app hosting MCP and simulator."""
    # Obtain the streamable HTTP Starlette app from the official MCP SDK
    # Streamable HTTP mounts at /mcp
    app = mcp.streamable_http_app(streamable_http_path="/mcp")

    # Add custom API & health routes
    app.routes.append(Route("/health", health_endpoint, methods=["GET"]))
    app.routes.append(Route("/api/simulator/chat", simulator_chat, methods=["POST"]))
    app.routes.append(Route("/api/simulator/decks", simulator_decks, methods=["GET"]))
    app.routes.append(Route("/", root_redirect, methods=["GET"]))

    # Mount static files for simulator UI if directory exists
    simulator_dir = os.path.join(os.path.dirname(__file__), "simulator")
    if os.path.exists(simulator_dir):
        app.mount("/simulator", StaticFiles(directory=simulator_dir, html=True), name="simulator")

    # Add CORS middleware to support web simulator and any web-based MCP clients
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    return app


app = create_app()


def main():
    """Run server on configured host and port."""
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    print("=" * 60)
    print("  StudyBuddy MCP Server - Voice-First Spaced Repetition")
    print(f"  MCP Streamable HTTP Endpoint: http://{host}:{port}/mcp")
    print(f"  Health Check:                 http://{host}:{port}/health")
    print(f"  Voice Simulator Web UI:       http://localhost:{port}/simulator/")
    print("=" * 60)
    uvicorn.run("server:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
