# StudyBuddy + VivaMate: Devpost Submission Package & Friction Log

This document contains everything needed for your final hackathon submission, demo video recording, and product feedback.

---

## 1. Devpost Submission Text

### Name
StudyBuddy (with VivaMate)

### Tagline
Your hands-free, voice-first study partner that remembers what you forget.

### Elevator Pitch
Students spend hours passively re-reading notes—one of the least effective ways to learn. Active recall and spaced repetition work exponentially better, but traditional flashcard apps require a screen and keyboard, making them useless while cooking, commuting, or walking.

**StudyBuddy** is a self-hosted Model Context Protocol (MCP) server that gives Alexa+ a lifelong memory for learning. It provides two integrated voice modes sharing a unified memory graph:
1. **Flashcard Spaced Repetition:** Fast spoken recall powered by the **SuperMemo-2 (SM-2)** algorithm.
2. **VivaMate Oral Exam Simulator:** Adaptive viva examinations where Alexa+ asks open-ended conceptual questions, dynamically increases or decreases difficulty (beginner $\leftrightarrow$ intermediate $\leftrightarrow$ advanced), drills down with probing follow-ups, and auto-schedules revisions for weak concepts.

---

### Key Features
1. **Hands-Free Active Recall & Viva:** Seamlessly practice flashcards or oral exams completely screen-free.
2. **SM-2 Spaced Repetition Engine:** Calculates optimal review intervals based on quality (0–5) and historical recall.
3. **Adaptive Viva & Follow-up Probing:** Probes with targeted follow-ups when scores indicate partial grasp (4–7/10), and scales difficulty dynamically.
4. **Shared Learning Memory:** Weak areas identified during viva automatically inform flashcard review priority, and vice-versa.
5. **Unified Revision Planner:** Consolidates due flashcards and scheduled topic revisions into one spoken forecast.
6. **AWS Bedrock Integration (AWS Builder Challenge):** Server-side conceptual evaluation using AWS Bedrock Converse API with academic rubric prompts.
7. **Live MCP Inspector:** Real-time visibility into tool execution and payload latency in the built-in simulator.

---

### How We Built It
- **Language & Core:** Python 3.11+, official `mcp` SDK (`MCPServer` / `FastMCP`)
- **Transport:** Streamable HTTP at `/mcp` adhering to the latest MCP specification (`2025-11-25+` / `2026-07-28`)
- **Algorithms:** SuperMemo-2 (SM-2) algorithm and dynamic difficulty progression state machine
- **Evaluation:** Dual evaluation via conversational rapidfuzz token similarity and AWS Bedrock Converse API (`studybuddy/evaluator.py`)
- **Database:** SQLite with tables for `cards`, `reviews`, `sessions`, `viva_sessions`, `viva_answers`, `weak_topics`, and `revisions`
- **Voice Simulator:** Single-page web app with Web Speech STT/TTS, hands-free auto-listening, and a live MCP tool call inspector panel
- **Testing:** 30 automated pytest unit tests covering SM-2, grading, viva follow-ups, difficulty progression, shared memory, and Bedrock mocking
- **Containerization:** Production Dockerfile ready for AWS App Runner, ECS, Render, or Fly.io

---

## 2. Product Feedback (Required for Judging)

### MCP Python SDK
- **Tool:** `mcp` Python SDK (v2.3.0)
- **Used for:** Implementing StudyBuddy MCP server, registering 11 tools, and serving Streamable HTTP transport.
- **Worked well:** Tool registration with `@mcp.tool()` is intuitive; automatic JSON serialization into `TextContent` is clean; Streamable HTTP handles session management out of the box.
- **Needs work:** The transition from v1 (`FastMCP`) to v2 (`MCPServer`) had breaking import path changes (`from mcp.server.mcpserver import MCPServer`). Clearer compatibility aliases in `__init__` would simplify upgrading legacy examples.
- **Onboarding:** Easy once the migration guide was consulted.
- **Would I build with it again:** Yes, absolutely. The standardization it brings to voice agent tool integration is unparalleled.

### AWS Bedrock Converse API (AWS Builder Challenge)
- **Tool:** AWS Bedrock Runtime (`boto3.client('bedrock-runtime').converse(...)`)
- **Used for:** Server-side oral exam response scoring against an academic rubric when model ID is provided.
- **Worked well:** The unified Converse API is significantly cleaner than legacy model-specific invoke APIs. Structured JSON output with low latency (<500ms on Haiku/Nova).
- **Needs work:** JSON schema enforcement mode in Converse API across all model families would eliminate regex parsing fallbacks.
- **Would I build with it again:** Yes, it is the best way to add model-agnostic grading to MCP servers.

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
| **0:00 - 0:25** | Open simulator or Alexa+. Show prompt. | *"Students spend hundreds of hours re-reading notes—one of the weakest ways to study. Spaced repetition and oral viva exams work exponentially better, but require either a screen or a live professor. Meet StudyBuddy: your hands-free, voice-first study partner powered by MCP and SM-2."* |
| **0:25 - 1:00** | Prompt *"Quiz me on Physics Chapter 3"*. | **You:** *"Alexa, quiz me on Physics Chapter 3."*<br>**Alexa:** *"Starting a 5-question quiz. Question 1: What is Newton's second law?"*<br>**You:** *"Force equals mass times acceleration."*<br>**Alexa:** *"Correct! You'll see this again in 6 days."* |
| **1:00 - 1:50** | Switch to VivaMate mode: *"Practice viva on Newtonian Mechanics"*. Show follow-up probe! | **You:** *"Alexa, practice viva on Newtonian Mechanics."*<br>**Alexa:** *"Starting a 3-question intermediate viva. I'll emphasize past weak areas like Rotational Dynamics. Question 1: Explain conservation of angular momentum with a spinning skater."*<br>**You:** *"They pull their arms in to spin faster."*<br>**Alexa (Follow-up Probe):** *"Good intuition! Let's explore that deeper: can you elaborate on how moment of inertia relates to angular velocity?"*<br>**You:** *"Angular momentum is moment of inertia times angular velocity, so smaller inertia forces higher velocity."*<br>**Alexa:** *"Spot on! Difficulty increased to advanced."* |
| **1:50 - 2:20** | Show **Live MCP Inspector** updating live with `record_answer`, `start_viva`, and `get_revision_plan`. | *"Notice the live MCP inspector on the right. Every voice interaction translates into an official MCP tool call over Streamable HTTP. The server adapts difficulty, triggers follow-ups, and schedules revision in SQLite."* |
| **2:20 - 2:45** | Show architecture diagram, Dockerfile, Bedrock evaluator, and 30 passing pytest tests. | *"StudyBuddy is built in Python with the official MCP SDK, integrates AWS Bedrock for the AWS Builder challenge, passes 30 unit tests, and packages with Docker for one-click deployment. Study anywhere, completely screen-free. Thank you!"* |
