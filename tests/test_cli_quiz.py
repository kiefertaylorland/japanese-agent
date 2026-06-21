from __future__ import annotations

import runpy
from datetime import date, timedelta
from types import SimpleNamespace

from typer.testing import CliRunner

from jp_agent import cli, db, quiz
from jp_agent.config import Paths
from jp_agent.models import CardSpec, GeneratedQuestion, Plan, StudyRequest, VerifiedQuestion
from jp_agent.vocab import load_all_vocab

runner = CliRunner()


def _insert_card(conn, card_id: str, mode: str, due_date: str, *, variant: str, level: str | None = None) -> None:
    conn.execute(
        """
        INSERT INTO cards (card_id, mode, level, variant, ease, interval, due_date, last_result, last_reviewed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL)
        """,
        (card_id, mode, level, variant, 2.0, 1, due_date),
    )
    conn.commit()


def test_cli_init_and_study_validation(monkeypatch, tmp_path, vocab_dir):
    paths = Paths(data_dir=vocab_dir, db_path=tmp_path / "app.db")
    vocab = load_all_vocab(vocab_dir)
    sync_calls: list[tuple[int, str]] = []
    run_calls: list[tuple[StudyRequest, object | None]] = []

    monkeypatch.setattr(cli, "resolve_paths", lambda db_path=None: paths)
    monkeypatch.setattr(cli, "load_all_vocab", lambda data_dir: vocab)
    monkeypatch.setattr(cli, "build_all_cards", lambda loaded: [CardSpec("hiragana:a:kana_to_romaji", "hiragana", None, "kana_to_romaji", "a")])
    monkeypatch.setattr(cli.db, "sync_cards", lambda conn, cards, today: sync_calls.append((len(cards), today)))
    monkeypatch.setattr(cli, "verify_vocab_hashes", lambda conn, data_dir, mode, level: None)
    monkeypatch.setattr(cli, "load_vocab_for_mode", lambda data_dir, mode, level: vocab)
    monkeypatch.setattr(cli, "run_quiz", lambda conn, request, loaded_vocab, llm: run_calls.append((request, llm)))
    monkeypatch.setattr(cli, "get_llm_config", lambda: "llm-config")

    init_result = runner.invoke(cli.app, ["init", "--sync", "--db", str(paths.db_path)])
    assert init_result.exit_code == 0
    assert "Synced cards from vocab files." in init_result.stdout
    assert "Initialized database" in init_result.stdout
    assert sync_calls and sync_calls[0][0] == 1

    study_result = runner.invoke(cli.app, ["study", "keigo", "--db", str(paths.db_path)])
    assert study_result.exit_code == 0
    assert run_calls and run_calls[0][0].mode == "keigo"
    assert run_calls[0][1] == "llm-config"

    invalid_mode = runner.invoke(cli.app, ["study", "bad"])
    assert invalid_mode.exit_code == 2
    assert "Mode must be one of" in invalid_mode.stdout

    missing_level = runner.invoke(cli.app, ["study", "kanji"])
    assert missing_level.exit_code == 2
    assert "Kanji mode requires --level" in missing_level.stdout

    invalid_level = runner.invoke(cli.app, ["study", "kanji", "--level", "N1"])
    assert invalid_level.exit_code == 2
    assert "Kanji level must be one of" in invalid_level.stdout


def test_cli_study_hash_failure_and_stats_output(monkeypatch, tmp_path, vocab_dir):
    paths = Paths(data_dir=vocab_dir, db_path=tmp_path / "stats.db")
    conn = db.connect(paths.db_path)
    db.ensure_schema(conn)
    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    reviewed_at = "2000-01-01T00:00:00+00:00"

    _insert_card(conn, "hiragana:a:kana_to_romaji", "hiragana", today, variant="kana_to_romaji")
    _insert_card(conn, "kanji:N5:日:kanji_to_meaning", "kanji", yesterday, variant="kanji_to_meaning", level="N5")
    conn.execute(
        """
        INSERT INTO reviews (card_id, reviewed_at, correct, response_ms, ease_before, ease_after, interval_before, interval_after)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("hiragana:a:kana_to_romaji", reviewed_at, 1, 100, 2.0, 2.1, 1, 2),
    )
    conn.commit()

    monkeypatch.setattr(cli, "resolve_paths", lambda db_path=None: paths)
    monkeypatch.setattr(cli, "verify_vocab_hashes", lambda conn, data_dir, mode, level: (_ for _ in ()).throw(ValueError("bad hashes")))

    failed = runner.invoke(cli.app, ["study", "hiragana", "--db", str(paths.db_path)])
    assert failed.exit_code == 1
    assert "bad hashes" in failed.stdout

    stats = runner.invoke(cli.app, ["stats", "--db", str(paths.db_path)])
    assert stats.exit_code == 0
    assert "Total cards: 2" in stats.stdout
    assert "Due cards: 2" in stats.stdout
    assert "Accuracy (7d): no reviews" in stats.stdout
    assert "Accuracy (30d): no reviews" in stats.stdout
    assert "By mode:" in stats.stdout


def test_cli_stats_accuracy_branches(monkeypatch, tmp_path, vocab_dir):
    paths = Paths(data_dir=vocab_dir, db_path=tmp_path / "reviews.db")
    conn = db.connect(paths.db_path)
    db.ensure_schema(conn)
    today = date.today().isoformat()
    recent = "2999-01-01T00:00:00+00:00"

    _insert_card(conn, "hiragana:a:kana_to_romaji", "hiragana", today, variant="kana_to_romaji")
    conn.execute(
        """
        INSERT INTO reviews (card_id, reviewed_at, correct, response_ms, ease_before, ease_after, interval_before, interval_after)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("hiragana:a:kana_to_romaji", recent, 1, 100, 2.0, 2.1, 1, 2),
    )
    conn.commit()

    monkeypatch.setattr(cli, "resolve_paths", lambda db_path=None: paths)
    result = runner.invoke(cli.app, ["stats", "--db", str(paths.db_path)])
    assert result.exit_code == 0
    assert "Accuracy (7d): 1/1 (100%)" in result.stdout
    assert "Accuracy (30d): 1/1 (100%)" in result.stdout


def test_cli_main_guard_executes(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr("typer.main.Typer.__call__", lambda self, *args, **kwargs: calls.append("called"))
    runpy.run_module("jp_agent.cli", run_name="__main__")
    assert calls == ["called"]


def test_run_quiz_handles_empty_plan_and_missing_card(monkeypatch, capsys):
    class EmptyPlanner:
        def plan(self, conn, request):
            return Plan(card_specs=[])

    monkeypatch.setattr(quiz, "PlannerAgent", lambda: EmptyPlanner())
    monkeypatch.setattr(quiz, "ContentGeneratorAgent", lambda vocab, llm: object())
    monkeypatch.setattr(quiz, "VerifierAgent", lambda: object())
    monkeypatch.setattr(quiz, "SrsAgent", lambda: object())
    quiz.run_quiz(None, StudyRequest("hiragana", None, None, 1, 1), SimpleNamespace(), None)
    assert "No cards available for review." in capsys.readouterr().out

    card = CardSpec("hiragana:a:kana_to_romaji", "hiragana", None, "kana_to_romaji", "a")

    class OnePlanner:
        def plan(self, conn, request):
            return Plan(card_specs=[card])

    monkeypatch.setattr(quiz, "PlannerAgent", lambda: OnePlanner())
    monkeypatch.setattr(quiz, "ContentGeneratorAgent", lambda vocab, llm: object())
    monkeypatch.setattr(quiz, "VerifierAgent", lambda: object())
    monkeypatch.setattr(quiz, "SrsAgent", lambda: object())
    monkeypatch.setattr(quiz.db, "fetch_card", lambda conn, card_id: None)
    quiz.run_quiz(None, StudyRequest("hiragana", None, None, 1, 1), SimpleNamespace(), None)
    assert "Skipping missing card: hiragana:a:kana_to_romaji" in capsys.readouterr().out


def test_run_quiz_retries_and_prints_keigo_metadata(monkeypatch, capsys):
    card = CardSpec("keigo:言う:plain_to_keigo", "keigo", None, "plain_to_keigo", "言う")
    card_row = {"card_id": card.card_id, "ease": 2.0, "interval": 1}
    calls: list[bool] = []

    class Planner:
        def plan(self, conn, request):
            return Plan(card_specs=[card])

    class Generator:
        def __init__(self, vocab, llm):
            pass

        def generate(self, _card, _request, _rng, *, use_llm=True):
            calls.append(use_llm)
            return GeneratedQuestion(
                prompt="pro\x00mpt",
                choices=["bad\x00", "worse", "best"],
                correct_index=2,
                explanation="exp\x00lanation",
                meta={"usage": "business", "type": "kenjogo"},
            )

    class Verifier:
        def __init__(self):
            self.calls = 0

        def verify(self, _card, question, vocab):
            self.calls += 1
            if self.calls == 1:
                return VerifiedQuestion(False, question, ["explanation includes non-whitelisted Japanese text"])
            return VerifiedQuestion(True, question, [])

    class Srs:
        def apply(self, conn, row, correct, elapsed_ms):
            return SimpleNamespace(interval_after=4)

    monkeypatch.setattr(quiz, "PlannerAgent", lambda: Planner())
    monkeypatch.setattr(quiz, "ContentGeneratorAgent", lambda vocab, llm: Generator(vocab, llm))
    monkeypatch.setattr(quiz, "VerifierAgent", Verifier)
    monkeypatch.setattr(quiz, "SrsAgent", lambda: Srs())
    monkeypatch.setattr(quiz.db, "fetch_card", lambda conn, card_id: card_row)
    monkeypatch.setattr(quiz, "_prompt_for_answer", lambda choice_count: 2)

    quiz.run_quiz(None, StudyRequest("keigo", None, "email", 1, 1), SimpleNamespace(), "llm")
    output = capsys.readouterr().out
    assert calls == [True, False]
    assert "Q1: prompt" in output
    assert "✔ Correct" in output
    assert "explanation" in output
    assert "Usage: business" in output
    assert "Politeness level: kenjogo" in output
    assert "Next review: 4 days" in output


def test_run_quiz_skips_invalid_question_and_handles_incorrect_answer(monkeypatch, capsys):
    invalid_card = CardSpec("hiragana:a:kana_to_romaji", "hiragana", None, "kana_to_romaji", "a")
    wrong_card = CardSpec("hiragana:i:kana_to_romaji", "hiragana", None, "kana_to_romaji", "i")
    rows = {
        invalid_card.card_id: {"card_id": invalid_card.card_id, "ease": 2.0, "interval": 1},
        wrong_card.card_id: {"card_id": wrong_card.card_id, "ease": 2.0, "interval": 1},
    }

    class Planner:
        def plan(self, conn, request):
            return Plan(card_specs=[invalid_card, wrong_card])

    class Generator:
        def __init__(self, vocab, llm):
            self.calls = 0

        def generate(self, card, request, rng, *, use_llm=True):
            self.calls += 1
            if card.card_id == invalid_card.card_id:
                raise RuntimeError("boom")
            return GeneratedQuestion("ask", ["one", "two", "three"], 1, "", {})

    class Verifier:
        def verify(self, card, question, vocab):
            return VerifiedQuestion(True, question, [])

    class Srs:
        def apply(self, conn, row, correct, elapsed_ms):
            return SimpleNamespace(interval_after=2)

    answers = iter([0])
    monkeypatch.setattr(quiz, "PlannerAgent", lambda: Planner())
    monkeypatch.setattr(quiz, "ContentGeneratorAgent", lambda vocab, llm: Generator(vocab, llm))
    monkeypatch.setattr(quiz, "VerifierAgent", lambda: Verifier())
    monkeypatch.setattr(quiz, "SrsAgent", lambda: Srs())
    monkeypatch.setattr(quiz.db, "fetch_card", lambda conn, card_id: rows[card_id])
    monkeypatch.setattr(quiz, "_prompt_for_answer", lambda choice_count: next(answers))

    quiz.run_quiz(None, StudyRequest("hiragana", None, None, 2, 1), SimpleNamespace(), None)
    output = capsys.readouterr().out
    assert "Skipping card due to invalid question: hiragana:a:kana_to_romaji" in output
    assert "Issues: boom" in output
    assert "✘ Incorrect. Correct answer: two" in output


def test_prompt_for_answer_retries_until_valid(monkeypatch, capsys):
    answers = iter(["x", "4", "2"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
    assert quiz._prompt_for_answer(3) == 1
    output = capsys.readouterr().out
    assert output.count("Please enter a number between 1 and 3.") == 2
