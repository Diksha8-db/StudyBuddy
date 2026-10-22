# StudyBuddy: Devpost Submission Package & Friction Log

This document contains everything needed for your final hackathon submission, demo video recording, and product feedback.

---

## 1. Devpost Submission Text

### Name
StudyBuddy

### Tagline
Your hands-free, voice-first study partner that remembers what you forget.

### Elevator Pitch
Students spend hours passively re-reading notes—one of the least effective ways to learn. Active recall and spaced repetition work exponentially better, but traditional flashcard apps require a screen and keyboard, making them useless while cooking, commuting, or walking.

**StudyBuddy** is a self-hosted Model Context Protocol (MCP) server that gives Alexa+ a lifelong memory for flashcards. Simply say *"Alexa, quiz me on Physics Chapter 3,"* and Alexa asks questions one at a time, grades spoken answers, schedules future reviews with the **SuperMemo-2 (SM-2)** algorithm, and pinpoints your weak topics.

---

### Key Features
1. **Hands-Free Active Recall:** Ask Alexa to quiz you while on the go.
2. **SM-2 Spaced Repetition:** Calculates review intervals based on recall quality (0–5) and historical mastery.
3. **Voice-First Design:** Concise responses without markdown, tailored for text-to-speech.
4. **Intelligent Spoken Grading:** Combines LLM assessment with rapidfuzz token similarity for natural spoken phrasing.
5. **Weak Topic Analytics:** Ranks topics by miss rate to focus study sessions where they matter most.
6. **Live MCP Inspector:** Real-time visibility into tool execution and payload latency.

---

### How We Built It
- **Language & Core:** Python 3.11+, official `mcp` SDK (`MCPServer` / `FastMCP`)
- **Transport:** Streamable HTTP at `/mcp` adhering to the `2025-11-25+` / `2026-07-28` specification
- **Algorithm:** SuperMemo-2 (SM-2) spaced repetition algorithm
- **Answer Grading:** Rapidfuzz token-set similarity fallback with tolerance for conversational speech
- **Database:** SQLite with tables for `cards`, `reviews`, and `sessions`
- **Voice Simulator:** Single-page web application with Web Speech STT/TTS, hands-free auto-listen, and a live MCP tool call inspector panel
- **Testing:** 21 automated pytest unit tests covering SM-2, grading, tools, and Starlette endpoints
- **Containerization:** Production Dockerfile ready for Render, Fly.io, Railway, or AWS App Runner

---

## 2. Product Feedback (Required for Judging)

### MCP Python SDK
- **Tool:** `mcp` Python SDK (v2.3.0)
- **Used for:** Implementing StudyBuddy MCP server, registering tools, and serving Streamable HTTP transport.
- **Worked well:** Tool registration with `@mcp.tool()` is intuitive; automatic JSON serialization into `TextContent` is clean; Streamable HTTP handles session management out of the box.
- **Needs work:** The transition from v1 (`FastMCP`) to v2 (`MCPServer`) had breaking import path changes (`from mcp.server.mcpserver import MCPServer`). Clearer compatibility aliases in `__init__` would simplify upgrading legacy examples.
- **Onboarding:** Easy once the migration guide was consulted.
- **Would I build with it again:** Yes, absolutely. The standardization it brings to tool integration is unparalleled.

---

## 3. Friction Log Entries (Bonus Scoring)

### Entry 1: MCP SDK V2 Import Rename
- **Task:** Initializing FastMCP server with Streamable HTTP.
- **Steps:** Attempted to import `from mcp.server.fastmcp import FastMCP`.
- **Expected:** Backwards-compatible import or deprecation warning.
- **Actual:** `ModuleNotFoundError` instructing migration to `mcp.server.mcpserver.MCPServer`.
- **Severity:** Medium.
- **Workaround:** Wrapped import in a `try...except` block aliasing `MCPServer as FastMCP`.
- **Suggestion:** Provide a transitional alias `from mcp.server.fastmcp import FastMCP` in `mcp 2.x` with a `DeprecationWarning` rather than raising `ModuleNotFoundError`.

### Entry 2: Spoken Answer Grading with Conversational Fillers
- **Task:** Accurately grading spoken student answers like *"Well, it is force equals mass times acceleration"*.
- **Steps:** Compared strict string equality or standard Levenshtein distance.
- **Expected:** Correctly recognize valid physics definitions despite filler words.
- **Actual:** Direct string comparisons penalize conversational voice variations.
- **Severity:** High for voice UX.
- **Workaround:** Implemented `rapidfuzz.fuzz.token_set_ratio` with regex normalization, granting full points ($\ge 85\%$) for key semantic token matches.
- **Suggestion:** Recommend token-set matching in voice MCP developer guidelines.

---

## 4. Demo Video Script (< 3 Minutes)

| Time | Visual | Spoken Script |
|---|---|---|
| **0:00 - 0:25** | Open simulator or Alexa+. Show prompt. | *"Students spend hundreds of hours re-reading notes—one of the weakest ways to study. Spaced repetition works, but flashcard apps chain you to a screen. Meet StudyBuddy: your hands-free, voice-first study partner powered by MCP and SM-2."* |
| **0:25 - 1:15** | Click Mic or prompt *"Quiz me on Physics Chapter 3"*. | **You:** *"Alexa, quiz me on Physics Chapter 3."*<br>**Alexa:** *"Starting a 5-question quiz. Question 1: What is Newton's second law?"*<br>**You:** *"Force equals mass times acceleration."*<br>**Alexa:** *"Correct! You'll see this again in 6 days. Question 2: What is the formula for linear momentum?"*<br>**You:** *"Momentum is speed?"*<br>**Alexa:** *"Not quite. Momentum is mass times velocity. I'll bring it back tomorrow."* |
| **1:15 - 1:50** | Show the **Live MCP Inspector** panel updating live with `grade_answer` and `start_quiz` arguments, latency, and response JSON. | *"Notice the live MCP inspector on the right. Every voice interaction translates into an official MCP tool call over Streamable HTTP. The SM-2 algorithm recalculates ease factors and intervals in SQLite with sub-25ms latency."* |
| **1:50 - 2:20** | Click *"What are my weak topics?"* and *"When should I review next?"*. | **You:** *"What are my weak topics?"*<br>**Alexa:** *"Your weakest topic is Momentum with a 50 percent miss rate. Would you like to drill those?"* |
| **2:20 - 2:45** | Show architecture diagram, Dockerfile, and passing pytest suite. | *"StudyBuddy is built in Python with the official MCP SDK, fully tested with 21 unit tests, and packaged with Docker for one-click deployment. Study anywhere, completely screen-free. Thank you!"* |
