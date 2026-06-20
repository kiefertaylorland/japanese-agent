from __future__ import annotations

import sqlite3
from datetime import date, timedelta

import pytest

from jp_agent import db
from jp_agent.agents.planner import PlannerAgent
from jp_agent.agents.srs import SrsAgent, update_srs
from jp_agent.cards import parse_vocab_key
from jp_agent.config import DEFAULT_DATA_DIRNAME, Paths, resolve_paths
from jp_agent.llm import get_llm_config
from jp_agent.models import CardSpec, StudyRequest
from jp_agent.utils import sanitize_lines, sanitize_text


def _insert_card(
    conn: sqlite3.Connection,
    card_id: str,
    mode: str,
    due_date: str,
    *,
    level: str | None = None,
    variant: str = "kana_to_romaji",
    ease: float = 2.0,
    interval: int = 1,
) -> None:
    conn.execute(
        """
        INSERT INTO cards (card_id, mode, level, variant, ease, interval, due_date, last_result, last_reviewed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL)
        """,
        (card_id, mode, level, variant, ease, interval, due_date),
    )
    conn.commit()


def test_resolve_paths_uses_overrides_and_env(monkeypatch, tmp_path):
    env_db = tmp_path / "env.db"
    monkeypatch.setenv("JP_AGENT_DB", str(env_db))

    from_env = resolve_paths()
    assert from_env.db_path == env_db.resolve()
    assert from_env.data_dir.name == DEFAULT_DATA_DIRNAME

    explicit = resolve_paths(str(tmp_path / "custom.db"), str(tmp_path / "custom-data"))
    assert explicit == Paths(
        data_dir=(tmp_path / "custom-data").resolve(),
        db_path=(tmp_path / "custom.db").resolve(),
    )


def test_sanitize_helpers_remove_control_characters():
    assert sanitize_text("a\x00b\nc") == "abc"
    assert sanitize_lines(["x\x7fy", "ok"]) == ["xy", "ok"]


def test_get_llm_config_handles_missing_and_present_env(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    assert get_llm_config() is None

    created: list[str] = []

    class FakeClient:
        def __init__(self, *, api_key: str) -> None:
            created.append(api_key)

    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-test")
    monkeypatch.setattr("openai.OpenAI", FakeClient)

    config = get_llm_config()
    assert config is not None
    assert config.model == "gpt-test"
    assert created == ["secret"]


@pytest.mark.parametrize(
    ("card_id", "mode", "expected"),
    [
        ("hiragana:a:kana_to_romaji", "hiragana", "a"),
        ("katakana:ア:romaji_to_kana", "katakana", "ア"),
        ("kanji:N5:日:kanji_to_meaning", "kanji", "日"),
        ("keigo:言う:plain_to_keigo", "keigo", "言う"),
        ("vocab:friend:english_to_japanese", "vocab", "friend"),
        ("survival:thank you:japanese_to_english", "survival", "thank you"),
    ],
)
def test_parse_vocab_key_valid_modes(card_id, mode, expected):
    assert parse_vocab_key(card_id, mode) == expected


@pytest.mark.parametrize(
    ("card_id", "mode", "message"),
    [
        ("hiragana:a", "hiragana", "Invalid card_id for kana"),
        ("kanji:N5:日", "kanji", "Invalid card_id for kanji"),
        ("keigo:言う", "keigo", "Invalid card_id for keigo"),
        ("vocab:friend", "vocab", "Invalid card_id for vocab"),
        ("survival:hello", "survival", "Invalid card_id for survival"),
        ("x", "unknown", "Unsupported mode for card_id parse"),
    ],
)
def test_parse_vocab_key_invalid_modes(card_id, mode, message):
    with pytest.raises(ValueError, match=message):
        parse_vocab_key(card_id, mode)


def test_database_helpers_and_stats(tmp_path):
    conn = db.connect(tmp_path / "nested" / "test.db")
    db.ensure_schema(conn)

    today = date.today().isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    assert db.get_vocab_hash(conn, "missing.json") is None
    db.upsert_vocab_hash(conn, "hiragana.json", "abc")
    db.upsert_vocab_hash(conn, "katakana.json", "def")
    assert db.list_vocab_hashes(conn) == {"hiragana.json": "abc", "katakana.json": "def"}

    cards = [
        CardSpec("hiragana:a:kana_to_romaji", "hiragana", None, "kana_to_romaji", "a"),
        CardSpec("kanji:N5:日:kanji_to_meaning", "kanji", "N5", "kanji_to_meaning", "日"),
    ]
    db.sync_cards(conn, cards, tomorrow)
    db.sync_cards(conn, [cards[1]], tomorrow)

    assert db.fetch_card(conn, "hiragana:a:kana_to_romaji") is None
    kanji_row = db.fetch_card(conn, "kanji:N5:日:kanji_to_meaning")
    assert kanji_row is not None

    due = db.fetch_due_cards(conn, "kanji", "N5", tomorrow, 5)
    upcoming = db.fetch_next_cards(conn, "kanji", "N5", today, 5)
    assert [row["card_id"] for row in due] == ["kanji:N5:日:kanji_to_meaning"]
    assert [row["card_id"] for row in upcoming] == ["kanji:N5:日:kanji_to_meaning"]

    db.update_review(
        conn,
        card_id="kanji:N5:日:kanji_to_meaning",
        correct=False,
        response_ms=321,
        ease_before=2.0,
        ease_after=1.8,
        interval_before=1,
        interval_after=3,
        due_date_iso=tomorrow,
    )
    updated = db.fetch_card(conn, "kanji:N5:日:kanji_to_meaning")
    assert updated is not None
    assert updated["last_result"] == 0
    assert updated["interval"] == 3
    assert db.stats_overview(conn) == {"total": 1}
    assert db.stats_due(conn, today) == 0
    assert db.stats_accuracy(conn, "1900-01-01T00:00:00+00:00") == (0, 1)
    assert [(row["mode"], row["total"], row["due"]) for row in db.stats_by_mode(conn)] == [
        ("kanji", 1, 0)
    ]


def test_planner_fills_from_upcoming_cards(tmp_path):
    conn = db.connect(tmp_path / "planner.db")
    db.ensure_schema(conn)

    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    _insert_card(conn, "hiragana:a:kana_to_romaji", "hiragana", tomorrow)

    plan = PlannerAgent().plan(conn, StudyRequest(mode="hiragana", level=None, context=None, count=1, seed=1))
    assert [card.card_id for card in plan.card_specs] == ["hiragana:a:kana_to_romaji"]


def test_planner_mixed_kana_fills_from_upcoming_cards(tmp_path):
    conn = db.connect(tmp_path / "planner-kana.db")
    db.ensure_schema(conn)

    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    _insert_card(conn, "hiragana:a:kana_to_romaji", "hiragana", tomorrow)
    _insert_card(conn, "katakana:ア:kana_to_romaji", "katakana", tomorrow)

    plan = PlannerAgent().plan(conn, StudyRequest(mode="kana", level=None, context=None, count=2, seed=1))
    assert {card.mode for card in plan.card_specs} == {"hiragana", "katakana"}


def test_srs_caps_and_persists_review(tmp_path):
    capped = update_srs(ease=2.5, interval=2, correct=True)
    floored = update_srs(ease=1.3, interval=2, correct=False)
    assert capped.ease_after == 2.5
    assert floored.ease_after == 1.3

    conn = db.connect(tmp_path / "srs.db")
    db.ensure_schema(conn)
    today = date.today().isoformat()
    _insert_card(
        conn,
        "hiragana:a:kana_to_romaji",
        "hiragana",
        today,
        ease=2.0,
        interval=3,
    )
    row = db.fetch_card(conn, "hiragana:a:kana_to_romaji")
    assert row is not None

    result = SrsAgent().apply(conn, row, True, 250)
    assert result.interval_after == 6
    assert db.stats_accuracy(conn, "1900-01-01T00:00:00+00:00") == (1, 1)
