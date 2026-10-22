# StudyBuddy MCP 🎓🎙️

> **Your hands-free, voice-first study partner that remembers what you forget.**
> Now featuring **VivaMate** oral exam mode with shared memory across flashcards and interactive vivas.

StudyBuddy is a self-hosted Model Context Protocol (MCP) server that empowers voice agents like **Alexa+** with active recall, oral exam simulation, and spaced repetition memory. Using the **SuperMemo-2 (SM-2)** algorithm and a shared knowledge graph in SQLite, StudyBuddy schedules flashcards, tracks weak topics, conducts adaptive oral exams with dynamic difficulty progression, and schedules targeted revision plans—completely screen-free.

---

## 🌟 Key Capabilities

- **Dual Study Modes with Shared Memory:**
  - **Flashcard Active Recall:** Bite-sized questions with SM-2 spaced repetition interval calculation.
  - **VivaMate Oral Exam Simulation:** Open-ended conceptual viva examinations with dynamic difficulty progression (beginner $\leftrightarrow$ intermediate $\leftrightarrow$ advanced) and adaptive probing follow-up questions.
- **Unified Memory Graph:** Weak areas identified in viva exams automatically schedule revisions and inform flashcard quizzes, and vice-versa.
- **Voice-First Design:** All tools return concise, natural `speech` fields without markdown, optimized for text-to-speech engines.
- **AWS Bedrock Evaluator (AWS Builder Challenge):** Server-side conceptual answer evaluation via AWS Bedrock Converse API when model ID is provided.
- **Streamable HTTP MCP Transport:** Fully compliant with the official MCP specification (`2025-11-25+` / `2026-07-28`) at `/mcp` alongside a `/health` endpoint.
- **Interactive Voice Simulator:** Built-in web client (`/simulator/`) with Web Speech STT/TTS, hands-free auto-listening, and real-time live MCP Inspector side panel.

---

## 🏛️ Architecture

```
                       +-----------------------------------------+
                       |               Voice Client              |
                       |  (Alexa+ Preview / Web Voice Simulator) |
                       +--------------------+--------------------+
                                            |
                                 Streamable HTTP /mcp
                                            v
                       +-----------------------------------------+
                       |          StudyBuddy MCP Server          |
                       |       FastMCP / MCPServer (:8000)       |
                       +----+-------------------------------+----+
                            |                               |
             +--------------+--------------+                |
             |                             |                |
             v                             v                v
  +--------------------+        +--------------------+  +--------------------+
  | Flashcard Engine   |        | VivaMate Engine    |  | AWS Bedrock        |
  | - SM-2 Algorithm   |        | - State Management |  | - Converse API     |
  | - rapidfuzz Grader |        | - Follow-up Probes |  | - Rubric Prompt    |
  | - Due Date Sched   |        | - Adaptive Diff    |  |   (Optional)       |
  +----------+---------+        +----------+---------+  +--------------------+
             |                             |
             +--------------+--------------+
                            |
                            v
               +---------------------------+
               |  Unified SQLite Database  |
               |  - cards, reviews         |
               |  - viva_sessions, answers |
               |  - weak_topics (shared)   |
               |  - revisions (shared)     |
               +---------------------------+
```

---

## 🛠️ MCP Tool Reference (11 Tools)

### 1. Flashcard Mode
| Tool | Parameters | Description |
|---|---|---|
| `add_flashcard` | `deck`, `question`, `answer`, `topic` | Adds a flashcard for spaced repetition review. |
| `list_decks` | *none* | Lists decks, total card counts, and cards due today. |
| `start_quiz` | `deck`, `num_questions`, `mode` (`due`/`weak`/`mixed`) | Starts active recall session (never reveals answers). |
| `grade_answer` | `session_id`, `card_id`, `user_answer`, `quality` | Grades answer, updates SM-2 schedule, advances session. |

### 2. VivaMate Oral Exam Mode
| Tool | Parameters | Description |
|---|---|---|
| `start_viva` | `topic`, `num_questions`, `difficulty` | Initializes viva session, looks up prior weak topics for focus, and instructs agent to ask Question 1. |
| `record_answer` | `session_id`, `question`, `answer`, `score`, `feedback`, `missed_points`, `is_follow_up` | Evaluates answer (0–10), triggers follow-ups (score 4–7), adapts difficulty, auto-saves weak areas ($\le 5$), and returns agent instructions. |
| `save_weak_topic` | `topic`, `reason`, `severity`, `source` | Manually flags or deduplicates a weak topic in shared memory. |
| `schedule_revision` | `topic`, `days_from_now`, `note` | Schedules a targeted revision session (e.g. "tomorrow", "in 3 days"). |

### 3. Shared Memory & Planning
| Tool | Parameters | Description |
|---|---|---|
| `get_weak_topics` | `deck` *(optional)*, `limit` *(default 3)* | Merges flashcard miss rates and viva weak spots into ranked priorities. |
| `get_revision_plan` | `deck` *(optional)*, `days_ahead` *(default 3)* | Consolidated view of due flashcards, scheduled revisions, and upcoming study load. |
| `schedule_review` | `deck` *(optional)*, `days_ahead` *(default 3)* | Backward-compatible alias for `get_revision_plan`. |

---

## 🎙️ Example Voice Transcripts

### Mode 1: Active Recall Flashcard Quiz
> **Student:** *"Alexa, quiz me on Physics Chapter 3."*  
> **Alexa:** *"Starting a 5-question quiz on Physics Chapter 3. Question 1: What is Newton's second law?"*  
> **Student:** *"Force equals mass times acceleration."*  
> **Alexa:** *"Correct! You'll see this card again in 6 days. Question 2: What is the formula for linear momentum?"*  
> **Student:** *"Momentum is speed?"*  
> **Alexa:** *"Not quite. Momentum is mass times velocity. I'll bring this card back tomorrow."*  

### Mode 2: VivaMate Adaptive Oral Exam
> **Student:** *"Alexa, practice viva on Newtonian Mechanics."*  
> **Alexa:** *"Starting a 3-question intermediate viva on Newtonian Mechanics. I'll emphasize your past weak areas like Rotational Dynamics. Question 1: Explain the conservation of angular momentum and how a spinning figure skater changes velocity."*  
> **Student:** *"The skater pulls in their arms to spin faster because mass is closer to the center."*  
> **Alexa (Follow-up Probe):** *"Good intuition, but let's explore that a bit deeper. Can you elaborate on how moment of inertia relates to angular velocity?"*  
> **Student:** *"Angular momentum is moment of inertia times angular velocity. Reducing moment of inertia forces angular velocity to increase."*  
> **Alexa (Difficulty Progression):** *"Spot on! Moving to Question 2 at advanced difficulty..."*  
> *(At end of viva)*  
> **Alexa:** *"Viva complete! You averaged 8.5 out of 10. I've scheduled a quick revision on torque for tomorrow."*  

---

## 🧪 Testing with MCP Inspector

To test the viva and flashcard workflows using the official MCP Inspector:

```bash
npx @modelcontextprotocol/inspector http://localhost:8000/mcp
```

### Viva Flow Test Steps:
1. Call `start_viva` with `{"topic": "Newtonian Mechanics", "num_questions": 2, "difficulty": "intermediate"}`.
   - Note the returned `session_id` and `focus_areas`.
2. Call `record_answer` with:
   ```json
   {
     "session_id": "<session_id>",
     "question": "Explain conservation of momentum.",
     "answer": "Total momentum is conserved.",
     "score": 6.0,
     "feedback": "Correct, but specify conditions.",
     "missed_points": ["isolated system requirement"],
     "is_follow_up": false
   }
   ```
   - Verify `next_action` returns `"ask_follow_up"` with `follow_up_hint`.
3. Call `record_answer` answering the follow-up with `is_follow_up: true` and `score: 9.0`.
   - Verify difficulty upgrades to `"advanced"`.
4. Call `get_revision_plan()` and `get_weak_topics()` to see the shared memory reflection!

---

## ⚡ AWS Bedrock Evaluation (AWS Builder Challenge)

When running in an environment with AWS credentials and `BEDROCK_MODEL_ID` set:

```bash
export BEDROCK_MODEL_ID="anthropic.claude-3-haiku-20240307-v1:0"
export AWS_REGION="us-east-1"
```

If `record_answer` is called without explicit `score` or `feedback`, the server automatically evaluates the response via `boto3 bedrock-runtime` Converse API against an academic rubric prompt in [studybuddy/evaluator.py](studybuddy/evaluator.py).

---

## 🚀 Local Quickstart

```bash
# Activate virtual environment
.\venv\Scripts\activate   # Windows
source venv/bin/activate  # macOS / Linux

# Install dependencies
pip install -r requirements.txt

# Run server
python server.py
```

Endpoints:
- **Streamable HTTP MCP:** `http://localhost:8000/mcp`
- **Health Check:** `http://localhost:8000/health`
- **Voice Simulator Web App:** `http://localhost:8000/simulator/`

---

## 🔬 Unit Tests

Run the full pytest suite (30 passing tests):

```bash
pytest -v
```

Tests cover SM-2 intervals, rapidfuzz grading, all 11 MCP tools, follow-up probe rules, dynamic difficulty adaptation, deduplication of weak topics, revision scheduling, merged memory, and AWS Bedrock Converse API mocking.

---

## 📄 License

MIT License. See [LICENSE](LICENSE) for details.
