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
            "version": "1.0.0",
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
    if session_id and current_card_id:
        # Active quiz session: student is answering the current question
        tool_name = "grade_answer"
        tool_args = {
            "session_id": session_id,
            "card_id": int(current_card_id),
            "user_answer": utterance,
        }
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
        # Parse simple "add card: question | answer" or defaults
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
            "session_id": parsed_data["session_id"],
            "card_id": parsed_data["card_id"],
            "total_questions": parsed_data.get("total_questions", 5),
            "current_index": parsed_data.get("current_index", 1),
            "question": parsed_data.get("question"),
        }
    elif tool_name == "grade_answer" and parsed_data.get("success"):
        if not parsed_data.get("is_finished"):
            updated_session = {
                "session_id": session_id,
                "card_id": parsed_data.get("next_card_id"),
                "total_questions": parsed_data.get("total_questions", 5),
                "current_index": parsed_data.get("next_question_index", 1),
                "question": parsed_data.get("next_question"),
            }
        else:
            updated_session = None  # Quiz complete

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
