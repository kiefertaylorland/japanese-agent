from __future__ import annotations

from datetime import date, timedelta

from jp_agent import db
from jp_agent.agents.planner import PlannerAgent
from jp_agent.models import StudyRequest


def test_planner_prefers_due_cards(tmp_path):
    conn = db.connect(tmp_path / "test.db")
    db.ensure_schema(conn)

    today = date.today().isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    conn.execute(
        """
        INSERT INTO cards (card_id, mode, level, variant, ease, interval, due_date, last_result, last_reviewed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL)
        """,
        ("hiragana:a:kana_to_romaji", "hiragana", None, "kana_to_romaji", 2.0, 1, today),
    )
    conn.execute(
        """
        INSERT INTO cards (card_id, mode, level, variant, ease, interval, due_date, last_result, last_reviewed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL)
        """,
        ("hiragana:i:kana_to_romaji", "hiragana", None, "kana_to_romaji", 2.0, 1, tomorrow),
    )
    conn.commit()

    planner = PlannerAgent()
    request = StudyRequest(mode="hiragana", level=None, context=None, count=1, seed=42)
    plan = planner.plan(conn, request)

    assert len(plan.card_specs) == 1
    assert plan.card_specs[0].card_id == "hiragana:a:kana_to_romaji"


def test_planner_mixes_kana_modes(tmp_path):
    conn = db.connect(tmp_path / "test.db")
    db.ensure_schema(conn)

    today = date.today().isoformat()

    conn.execute(
        """
        INSERT INTO cards (card_id, mode, level, variant, ease, interval, due_date, last_result, last_reviewed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL)
        """,
        ("hiragana:a:kana_to_romaji", "hiragana", None, "kana_to_romaji", 2.0, 1, today),
    )
    conn.execute(
        """
        INSERT INTO cards (card_id, mode, level, variant, ease, interval, due_date, last_result, last_reviewed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL)
        """,
        ("katakana:ア:kana_to_romaji", "katakana", None, "kana_to_romaji", 2.0, 1, today),
    )
    conn.commit()

    planner = PlannerAgent()
    request = StudyRequest(mode="kana", level=None, context=None, count=2, seed=42)
    plan = planner.plan(conn, request)

    modes = {spec.mode for spec in plan.card_specs}
    assert modes == {"hiragana", "katakana"}
