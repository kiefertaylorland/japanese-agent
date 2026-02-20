from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from jp_agent.models import CardSpec


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cards (
            card_id TEXT PRIMARY KEY,
            mode TEXT NOT NULL,
            level TEXT,
            variant TEXT NOT NULL,
            ease REAL NOT NULL,
            interval INTEGER NOT NULL,
            due_date TEXT NOT NULL,
            last_result INTEGER,
            last_reviewed_at TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY,
            card_id TEXT NOT NULL,
            reviewed_at TEXT NOT NULL,
            correct INTEGER NOT NULL,
            response_ms INTEGER NOT NULL,
            ease_before REAL NOT NULL,
            ease_after REAL NOT NULL,
            interval_before INTEGER NOT NULL,
            interval_after INTEGER NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS vocab_files (
            path TEXT PRIMARY KEY,
            sha256 TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cards_due_date ON cards(due_date)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_reviews_reviewed_at ON reviews(reviewed_at)")
    conn.commit()


def upsert_vocab_hash(conn: sqlite3.Connection, path: str, sha256: str) -> None:
    conn.execute(
        """
        INSERT INTO vocab_files (path, sha256, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(path) DO UPDATE SET
            sha256=excluded.sha256,
            updated_at=excluded.updated_at
        """,
        (path, sha256, _utc_now_iso()),
    )
    conn.commit()


def get_vocab_hash(conn: sqlite3.Connection, path: str) -> str | None:
    row = conn.execute("SELECT sha256 FROM vocab_files WHERE path = ?", (path,)).fetchone()
    if row is None:
        return None
    return str(row["sha256"])


def list_vocab_hashes(conn: sqlite3.Connection) -> dict[str, str]:
    rows = conn.execute("SELECT path, sha256 FROM vocab_files").fetchall()
    return {str(row["path"]): str(row["sha256"]) for row in rows}


def sync_cards(conn: sqlite3.Connection, cards: list[CardSpec], today_iso: str) -> None:
    existing_rows = conn.execute("SELECT card_id FROM cards").fetchall()
    existing_ids = {str(row["card_id"]) for row in existing_rows}
    new_ids = {card.card_id for card in cards}

    to_insert = [card for card in cards if card.card_id not in existing_ids]
    to_delete = existing_ids - new_ids

    for card in to_insert:
        conn.execute(
            """
            INSERT INTO cards (card_id, mode, level, variant, ease, interval, due_date, last_result, last_reviewed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL)
            """,
            (
                card.card_id,
                card.mode,
                card.level,
                card.variant,
                2.0,
                1,
                today_iso,
            ),
        )

    if to_delete:
        conn.executemany("DELETE FROM cards WHERE card_id = ?", [(card_id,) for card_id in to_delete])

    conn.commit()


def fetch_due_cards(
    conn: sqlite3.Connection,
    mode: str,
    level: str | None,
    today_iso: str,
    limit: int,
    randomize: bool = False,
) -> list[sqlite3.Row]:
    order_clause = "RANDOM()" if randomize else "due_date ASC"
    if level:
        return conn.execute(
            """
            SELECT * FROM cards
            WHERE mode = ? AND level = ? AND due_date <= ?
            ORDER BY """
            + order_clause
            + """
            LIMIT ?
            """,
            (mode, level, today_iso, limit),
        ).fetchall()
    return conn.execute(
        """
        SELECT * FROM cards
        WHERE mode = ? AND due_date <= ?
        ORDER BY """
        + order_clause
        + """
        LIMIT ?
        """,
        (mode, today_iso, limit),
    ).fetchall()


def fetch_next_cards(
    conn: sqlite3.Connection,
    mode: str,
    level: str | None,
    today_iso: str,
    limit: int,
    randomize: bool = False,
) -> list[sqlite3.Row]:
    order_clause = "RANDOM()" if randomize else "due_date ASC"
    if level:
        return conn.execute(
            """
            SELECT * FROM cards
            WHERE mode = ? AND level = ? AND due_date > ?
            ORDER BY """
            + order_clause
            + """
            LIMIT ?
            """,
            (mode, level, today_iso, limit),
        ).fetchall()
    return conn.execute(
        """
        SELECT * FROM cards
        WHERE mode = ? AND due_date > ?
        ORDER BY """
        + order_clause
        + """
        LIMIT ?
        """,
        (mode, today_iso, limit),
    ).fetchall()


def fetch_card(conn: sqlite3.Connection, card_id: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM cards WHERE card_id = ?", (card_id,)).fetchone()


def update_review(
    conn: sqlite3.Connection,
    card_id: str,
    correct: bool,
    response_ms: int,
    ease_before: float,
    ease_after: float,
    interval_before: int,
    interval_after: int,
    due_date_iso: str,
) -> None:
    conn.execute(
        """
        UPDATE cards
        SET ease = ?, interval = ?, due_date = ?, last_result = ?, last_reviewed_at = ?
        WHERE card_id = ?
        """,
        (
            ease_after,
            interval_after,
            due_date_iso,
            1 if correct else 0,
            _utc_now_iso(),
            card_id,
        ),
    )
    conn.execute(
        """
        INSERT INTO reviews (card_id, reviewed_at, correct, response_ms, ease_before, ease_after, interval_before, interval_after)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            card_id,
            _utc_now_iso(),
            1 if correct else 0,
            response_ms,
            ease_before,
            ease_after,
            interval_before,
            interval_after,
        ),
    )
    conn.commit()


def stats_overview(conn: sqlite3.Connection) -> dict[str, int]:
    row = conn.execute("SELECT COUNT(*) AS total FROM cards").fetchone()
    total = int(row["total"]) if row else 0
    return {"total": total}


def stats_due(conn: sqlite3.Connection, today_iso: str) -> int:
    row = conn.execute("SELECT COUNT(*) AS due FROM cards WHERE due_date <= ?", (today_iso,)).fetchone()
    return int(row["due"]) if row else 0


def stats_accuracy(conn: sqlite3.Connection, since_iso: str) -> tuple[int, int]:
    row = conn.execute(
        """
        SELECT SUM(correct) AS correct, COUNT(*) AS total
        FROM reviews
        WHERE reviewed_at >= ?
        """,
        (since_iso,),
    ).fetchone()
    if row is None:
        return (0, 0)
    correct = int(row["correct"] or 0)
    total = int(row["total"] or 0)
    return (correct, total)


def stats_by_mode(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT mode, COUNT(*) AS total, SUM(CASE WHEN due_date <= DATE('now') THEN 1 ELSE 0 END) AS due
        FROM cards
        GROUP BY mode
        ORDER BY mode
        """
    ).fetchall()
