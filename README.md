# StudyBuddy MCP 🎓🎙️

> **Your hands-free, voice-first study partner that remembers what you forget.**

StudyBuddy is a self-hosted Model Context Protocol (MCP) server that empowers voice agents like **Alexa+** with active recall and spaced-repetition memory. Using the proven **SuperMemo-2 (SM-2)** algorithm, StudyBuddy schedules flashcards based on how well you remember them, pinpoints your weak topics, and conducts interactive spoken quizzes—completely screen-free.

---

## 🌟 Key Features

- **Hands-Free Active Recall:** Ask Alexa to quiz you while cooking, walking, or commuting.
- **SM-2 Spaced Repetition:** Calculates optimal review intervals based on answer quality (0–5) and historical recall.
- **Voice-Optimized Responses:** Every tool returns a concise, natural `speech` field without markdown, formatted specifically for text-to-speech.
- **Intelligent Spoken Grading:** Supports LLM quality ratings with automatic fuzzy matching (`rapidfuzz`) for conversational answer variations.
- **Weak Topic Analytics:** Aggregates miss rates across review sessions to recommend high-impact topics for practice.
- **Official MCP SDK (Streamable HTTP):** Built on the latest MCP specification (`2025-11-25+` / `2026-07-28`), exposing standard tools at `/mcp` alongside a `/health` endpoint.
- **Interactive Voice Simulator:** Built-in web client (`/simulator/`) with Web Speech STT/TTS and a live MCP Inspector logging every tool invocation in real-time.

---

## 🛠️ MCP Tool Reference (6 Tools)

| Tool | Parameters | Description |
|---|---|---|
| `add_flashcard` | `deck`, `question`, `answer`, `topic` *(optional)* | Adds a new flashcard to a deck for future spaced repetition review. |
| `list_decks` | *none* | Lists all decks, total card counts, and cards currently due for review. |
| `start_quiz` | `deck`, `num_questions` *(default 5)*, `mode` (`due` / `weak` / `mixed`) | Starts an active recall session, returning session ID and first question (never reveals answer). |
| `grade_answer` | `session_id`, `card_id`, `user_answer`, `quality` *(0–5, optional)* | Grades the spoken answer, updates SM-2 schedule, logs review, advances session, and returns verdict + next question or final score. |
| `get_weak_topics` | `deck` *(optional)*, `limit` *(default 3)* | Ranks topics by historical miss rate to identify study gaps. |
| `schedule_review` | `deck` *(optional)*, `days_ahead` *(default 3)* | Checks cards due today and upcoming schedule for the next several days. |

---

## 🧠 Spaced Repetition (SM-2) Logic

StudyBuddy implements SuperMemo-2 (SM-2):
1. **Quality Scale (0–5):**
   - $q \ge 3$: Successful recall.
   - $q < 3$: Failed recall (resets consecutive repetition count to 0 and schedules review for tomorrow).
2. **Interval Calculation:**
   - Repetition 0: Interval = 1 day.
   - Repetition 1: Interval = 6 days.
   - Repetition $n \ge 2$: $\text{Interval} = \text{round}(\text{Previous Interval} \times \text{Ease Factor})$.
3. **Easiness Factor Update:**
   $$\text{Ease} = \max(1.3, \text{Ease} + 0.1 - (5 - q) \times (0.08 + (5 - q) \times 0.02))$$
4. **Grading Engine:**
   - If `quality` is provided (e.g., Alexa+ LLM assessment), it is used directly.
   - If omitted, `rapidfuzz` performs token similarity against canonical answers:
     - $\ge 85\%$: Quality 5 (Correct)
     - $60\% - 84\%$: Quality 3 (Partial)
     - $< 60\%$: Quality 2 (Incorrect)

---

## 🏗️ Architecture

```
                 +-----------------------------------------+
                 |             Voice Client                |
                 |  (Alexa+ Preview / Web Voice Simulator) |
                 +--------------------+--------------------+
                                      |
                           Streamable HTTP /mcp
                                      v
                 +-----------------------------------------+
                 |          StudyBuddy MCP Server          |
                 |      FastMCP / MCPServer (Port 8000)    |
                 +----+-------------------------------+----+
                      |                               |
                      v                               v
           +--------------------+           +--------------------+
           |  SM-2 Engine &     |           |  SQLite Database   |
           |  rapidfuzz Grader  |           |  (cards, reviews,  |
           +--------------------+           |   sessions)        |
                                            +--------------------+
```

---

## 🚀 Quickstart & Local Setup

### Prerequisites
- Python 3.11+
- Git

### 1. Clone & Set Up Virtual Environment

```bash
git clone https://github.com/your-username/studybuddy-mcp.git
cd studybuddy-mcp

# Create and activate virtual environment
python -m venv venv

# Windows
.\venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Run the MCP Server

```bash
python server.py
```

The server will initialize SQLite (`studybuddy.db`), seed the demo deck **Physics Chapter 3** (10 cards), and start listening on port 8000:
- **MCP Endpoint (Streamable HTTP):** `http://localhost:8000/mcp`
- **Health Check:** `http://localhost:8000/health`
- **Interactive Voice Simulator:** `http://localhost:8000/simulator/`

---

## 🧪 Testing with MCP Inspector

To test the MCP server using the official Model Context Protocol Inspector:

```bash
npx @modelcontextprotocol/inspector http://localhost:8000/mcp
```

1. Select transport **Streamable HTTP**.
2. Connect to `http://localhost:8000/mcp`.
3. In the Inspector UI, test invoking:
   - `list_decks()`
   - `start_quiz(deck="Physics Chapter 3", num_questions=2)`
   - `grade_answer(session_id="...", card_id=1, user_answer="force equals mass times acceleration")`
   - `get_weak_topics()`
   - `schedule_review()`

---

## 🎙️ Interactive Voice Simulator

Open **`http://localhost:8000/simulator/`** in Chrome, Edge, or Safari:
- Click the **Mic** button (or enable **Hands-Free** mode) and speak naturally.
- Use quick action chips:
  - *"Quiz me on Physics Chapter 3"*
  - *"What are my weak topics?"*
  - *"When should I review next?"*
  - *"List my decks"*
- The **Live MCP Inspector** on the right side panel shows every tool call, input argument, and execution latency live!

---

## 🔬 Unit Tests

Run the comprehensive pytest suite covering SM-2 calculations, grading thresholds, database transactions, tool contracts, and HTTP endpoints:

```bash
pytest -v
```

All 21 test cases execute in ~1 second.

---

## 🐳 Docker & Cloud Deployment

### Docker

Build and run the container locally:

```bash
docker build -t studybuddy-mcp .
docker run -p 8000:8000 -e PORT=8000 studybuddy-mcp
```

### Render / Fly.io / Railway

- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `python server.py`
- **Health Check Path:** `/health`
- **Port:** Bind to environment variable `PORT`.

### AWS (App Runner / ECS)

1. Push Docker image to Amazon ECR.
2. Create an AWS App Runner service pointing to the container.
3. Configure port `8000` and health check `/health`.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
