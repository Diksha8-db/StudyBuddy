"""
SQLite Database layer for StudyBuddy.

Handles schema creation, indexes, connections, and demo deck seeding.
"""

import json
import os
import sqlite3
import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Optional

DEFAULT_DB_PATH = os.environ.get("STUDYBUDDY_DB_PATH", "studybuddy.db")

SEED_PHYSICS_CARDS = [
    {
        "topic": "Newton's Laws",
        "question": "What is Newton's first law of motion?",
        "answer": "An object remains at rest or in uniform motion unless acted upon by a net external force.",
    },
    {
        "topic": "Newton's Laws",
        "question": "What is Newton's second law of motion?",
        "answer": "Force equals mass times acceleration.",
    },
    {
        "topic": "Newton's Laws",
        "question": "What is Newton's third law of motion?",
        "answer": "For every action there is an equal and opposite reaction.",
    },
    {
        "topic": "Momentum",
        "question": "What is the formula for linear momentum?",
        "answer": "Momentum equals mass times velocity.",
    },
    {
        "topic": "Momentum",
        "question": "What is the principle of conservation of momentum?",
        "answer": "The total momentum of an isolated system remains constant if no external net force acts on it.",
    },
    {
        "topic": "Friction",
        "question": "What is the difference between static and kinetic friction?",
        "answer": "Static friction prevents motion while kinetic friction opposes motion of an already moving object.",
    },
    {
        "topic": "Work and Energy",
        "question": "What is the formula for kinetic energy?",
        "answer": "Kinetic energy equals one half mass times velocity squared.",
    },
    {
        "topic": "Work and Energy",
        "question": "What is the work-energy theorem?",
        "answer": "The net work done on an object equals the change in its kinetic energy.",
    },
    {
        "topic": "Momentum",
        "question": "What is impulse in physics?",
        "answer": "Impulse is the change in momentum or force multiplied by the elapsed time.",
    },
    {
        "topic": "Friction",
        "question": "What is the coefficient of friction?",
        "answer": "The ratio of the frictional force between two bodies to the normal force pressing them together.",
    },
]


from contextlib import contextmanager


class Database:
    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        self.init_db()

    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init_db(self) -> None:
        """Create tables if they don't exist and seed default data."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # 1. Cards table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cards (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    deck TEXT NOT NULL,
                    topic TEXT,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    ease_factor REAL DEFAULT 2.5,
                    interval_days INTEGER DEFAULT 0,
                    repetitions INTEGER DEFAULT 0,
                    due_date TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
            """)

            # 2. Reviews table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    card_id INTEGER NOT NULL,
                    quality INTEGER NOT NULL,
                    correct BOOLEAN NOT NULL,
                    user_answer TEXT,
                    reviewed_at TEXT NOT NULL,
                    FOREIGN KEY (card_id) REFERENCES cards(id) ON DELETE CASCADE
                );
            """)

            # 3. Sessions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    deck TEXT NOT NULL,
                    card_ids TEXT NOT NULL,
                    current_index INTEGER DEFAULT 0,
                    correct_count INTEGER DEFAULT 0,
                    started_at TEXT NOT NULL,
                    finished_at TEXT
                );
            """)

            # Create useful indexes for fast quiz selection & analytics
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cards_deck ON cards(deck);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cards_due ON cards(due_date);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_reviews_card ON reviews(card_id);")

            conn.commit()

        # Seed demo deck
        self.seed_demo_deck()

    def seed_demo_deck(self) -> None:
        """Seed demo deck 'Physics Chapter 3' if empty."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM cards WHERE deck = 'Physics Chapter 3'")
            count = cursor.fetchone()[0]

            if count == 0:
                today_str = date.today().isoformat()
                now_str = datetime.now().isoformat()
                for card in SEED_PHYSICS_CARDS:
                    cursor.execute(
                        """
                        INSERT INTO cards (deck, topic, question, answer, ease_factor, interval_days, repetitions, due_date, created_at)
                        VALUES (?, ?, ?, ?, 2.5, 0, 0, ?, ?)
                        """,
                        (
                            "Physics Chapter 3",
                            card["topic"],
                            card["question"],
                            card["answer"],
                            today_str,
                            now_str,
                        ),
                    )
                conn.commit()

    def add_card(self, deck: str, question: str, answer: str, topic: Optional[str] = None) -> int:
        """Add a new card to a deck."""
        today_str = date.today().isoformat()
        now_str = datetime.now().isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO cards (deck, topic, question, answer, ease_factor, interval_days, repetitions, due_date, created_at)
                VALUES (?, ?, ?, ?, 2.5, 0, 0, ?, ?)
                """,
                (deck.strip(), topic.strip() if topic else None, question.strip(), answer.strip(), today_str, now_str),
            )
            conn.commit()
            return cursor.lastrowid

    def get_card(self, card_id: int) -> Optional[Dict[str, Any]]:
        """Get card by ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM cards WHERE id = ?", (card_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def list_decks(self) -> List[Dict[str, Any]]:
        """List all decks with card count and due count."""
        today_str = date.today().isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT deck,
                       COUNT(*) as total_cards,
                       SUM(CASE WHEN due_date <= ? THEN 1 ELSE 0 END) as due_cards
                FROM cards
                GROUP BY deck
                ORDER BY deck ASC
                """,
                (today_str,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_cards_for_quiz(self, deck: str, limit: int = 5, mode: str = "mixed") -> List[Dict[str, Any]]:
        """
        Select cards for a quiz based on mode: 'due', 'weak', or 'mixed'.
        """
        today_str = date.today().isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()

            if mode == "due":
                cursor.execute(
                    """
                    SELECT * FROM cards
                    WHERE deck = ? AND due_date <= ?
                    ORDER BY due_date ASC, id ASC
                    LIMIT ?
                    """,
                    (deck, today_str, limit),
                )
                selected = [dict(r) for r in cursor.fetchall()]

                # If not enough due cards, fill with other cards in the deck
                if len(selected) < limit:
                    existing_ids = tuple(c["id"] for c in selected) or (-1,)
                    cursor.execute(
                        f"""
                        SELECT * FROM cards
                        WHERE deck = ? AND id NOT IN ({','.join(['?']*len(existing_ids))})
                        ORDER BY RANDOM()
                        LIMIT ?
                        """,
                        (deck, *existing_ids, limit - len(selected)),
                    )
                    selected.extend([dict(r) for r in cursor.fetchall()])
                return selected

            elif mode == "weak":
                # Order by highest miss rate
                cursor.execute(
                    """
                    SELECT c.*,
                           COALESCE(SUM(CASE WHEN r.correct = 0 THEN 1 ELSE 0 END), 0) as misses
                    FROM cards c
                    LEFT JOIN reviews r ON c.id = r.card_id
                    WHERE c.deck = ?
                    GROUP BY c.id
                    ORDER BY misses DESC, c.due_date ASC
                    LIMIT ?
                    """,
                    (deck, limit),
                )
                return [dict(r) for r in cursor.fetchall()]

            else:  # mixed mode
                # Prioritize: 1. due cards, 2. weak cards (past misses), 3. new cards (repetitions == 0)
                cursor.execute(
                    """
                    SELECT c.*,
                           CASE WHEN c.due_date <= ? THEN 0 ELSE 1 END as is_overdue_rank,
                           COALESCE(SUM(CASE WHEN r.correct = 0 THEN 1 ELSE 0 END), 0) as misses
                    FROM cards c
                    LEFT JOIN reviews r ON c.id = r.card_id
                    WHERE c.deck = ?
                    GROUP BY c.id
                    ORDER BY is_overdue_rank ASC, misses DESC, c.repetitions ASC, RANDOM()
                    LIMIT ?
                    """,
                    (today_str, deck, limit),
                )
                return [dict(r) for r in cursor.fetchall()]

    def update_card_sm2(
        self,
        card_id: int,
        repetitions: int,
        interval_days: int,
        ease_factor: float,
        due_date: str,
    ) -> None:
        """Update SM-2 fields on a card."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE cards
                SET repetitions = ?, interval_days = ?, ease_factor = ?, due_date = ?
                WHERE id = ?
                """,
                (repetitions, interval_days, ease_factor, due_date, card_id),
            )
            conn.commit()

    def log_review(
        self,
        card_id: int,
        quality: int,
        correct: bool,
        user_answer: Optional[str] = None,
    ) -> int:
        """Log a review attempt."""
        now_str = datetime.now().isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO reviews (card_id, quality, correct, user_answer, reviewed_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (card_id, quality, 1 if correct else 0, user_answer, now_str),
            )
            conn.commit()
            return cursor.lastrowid

    def create_session(self, deck: str, card_ids: List[int]) -> str:
        """Create a new quiz session."""
        session_id = f"quiz_{uuid.uuid4().hex[:8]}"
        now_str = datetime.now().isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO sessions (id, deck, card_ids, current_index, correct_count, started_at)
                VALUES (?, ?, ?, 0, 0, ?)
                """,
                (session_id, deck, json.dumps(card_ids), now_str),
            )
            conn.commit()
            return session_id

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Fetch session by ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
            row = cursor.fetchone()
            if not row:
                return None
            res = dict(row)
            res["card_ids"] = json.loads(res["card_ids"])
            return res

    def advance_session(self, session_id: str, is_correct: bool) -> Dict[str, Any]:
        """Advance session index and increment correct count if applicable."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT card_ids, current_index, correct_count FROM sessions WHERE id = ?", (session_id,))
            row = cursor.fetchone()
            if not row:
                raise ValueError(f"Session {session_id} not found.")

            card_ids = json.loads(row["card_ids"])
            new_index = row["current_index"] + 1
            new_correct = row["correct_count"] + (1 if is_correct else 0)
            finished_at = datetime.now().isoformat() if new_index >= len(card_ids) else None

            cursor.execute(
                """
                UPDATE sessions
                SET current_index = ?, correct_count = ?, finished_at = ?
                WHERE id = ?
                """,
                (new_index, new_correct, finished_at, session_id),
            )
            conn.commit()

            return {
                "session_id": session_id,
                "card_ids": card_ids,
                "current_index": new_index,
                "correct_count": new_correct,
                "total_questions": len(card_ids),
                "is_finished": new_index >= len(card_ids),
            }

    def get_weak_topics(self, deck: Optional[str] = None, limit: int = 3) -> List[Dict[str, Any]]:
        """Rank topics by miss rate over reviews."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            where_clause = "WHERE c.topic IS NOT NULL AND c.topic != ''"
            params: List[Any] = []
            if deck:
                where_clause += " AND c.deck = ?"
                params.append(deck)

            query = f"""
                SELECT c.topic,
                       COUNT(r.id) as total_reviews,
                       SUM(CASE WHEN r.correct = 0 THEN 1 ELSE 0 END) as missed_count,
                       ROUND(CAST(SUM(CASE WHEN r.correct = 0 THEN 1 ELSE 0 END) AS REAL) / COUNT(r.id), 2) as miss_rate
                FROM reviews r
                JOIN cards c ON r.card_id = c.id
                {where_clause}
                GROUP BY c.topic
                HAVING COUNT(r.id) > 0
                ORDER BY miss_rate DESC, missed_count DESC, total_reviews DESC
                LIMIT ?
            """
            params.append(limit)
            cursor.execute(query, tuple(params))
            return [dict(r) for r in cursor.fetchall()]

    def schedule_review(self, deck: Optional[str] = None, days_ahead: int = 3) -> Dict[str, Any]:
        """Get counts of cards due today and upcoming for the next days_ahead days."""
        today = date.today()
        today_str = today.isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()

            deck_filter = "AND deck = ?" if deck else ""
            params: List[Any] = [today_str]
            if deck:
                params.append(deck)

            # Cards due today or overdue
            cursor.execute(
                f"""
                SELECT COUNT(*) FROM cards
                WHERE due_date <= ? {deck_filter}
                """,
                tuple(params),
            )
            due_today = cursor.fetchone()[0]

            upcoming = []
            for i in range(1, days_ahead + 1):
                target_date = (today + datetime.timedelta(days=i) if hasattr(datetime, "timedelta") else today + (date.fromordinal(today.toordinal() + i) - today)).isoformat()
                from datetime import timedelta
                target_date_str = (today + timedelta(days=i)).isoformat()
                u_params: List[Any] = [target_date_str]
                if deck:
                    u_params.append(deck)
                cursor.execute(
                    f"""
                    SELECT COUNT(*) FROM cards
                    WHERE due_date = ? {deck_filter}
                    """,
                    tuple(u_params),
                )
                count = cursor.fetchone()[0]
                upcoming.append({"date": target_date_str, "due_count": count})

            total_upcoming = sum(u["due_count"] for u in upcoming)
            return {
                "due_today": due_today,
                "upcoming_days": upcoming,
                "total_due_in_window": due_today + total_upcoming,
            }
