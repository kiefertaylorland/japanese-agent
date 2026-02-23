from __future__ import annotations

import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import typer

from jp_agent import db
from jp_agent.cards import build_all_cards
from jp_agent.config import resolve_paths
from jp_agent.llm import get_llm_config
from jp_agent.models import StudyRequest
from jp_agent.quiz import run_quiz
from jp_agent.utils import sanitize_text
from jp_agent.vocab import (
    EXPECTED_FILES,
    compute_sha256,
    load_all_vocab,
    load_vocab_for_mode,
    resolve_vocab_path,
    verify_vocab_hashes,
)

app = typer.Typer(no_args_is_help=True)


@app.command()
def init(
    sync: bool = typer.Option(False, "--sync", help="Build or update cards from vocab files"),
    db_path: str | None = typer.Option(None, "--db", help="Path to SQLite DB"),
) -> None:
    paths = resolve_paths(db_path)
    conn = db.connect(paths.db_path)
    db.ensure_schema(conn)

    for filename in EXPECTED_FILES.values():
        vocab_path = resolve_vocab_path(paths.data_dir, filename)
        sha = compute_sha256(vocab_path)
        db.upsert_vocab_hash(conn, filename, sha)

    if sync:
        vocab = load_all_vocab(paths.data_dir)
        cards = build_all_cards(vocab)
        db.sync_cards(conn, cards, date.today().isoformat())
        print("Synced cards from vocab files.")

    print(f"Initialized database at {paths.db_path}")


@app.command()
def study(
    mode: str = typer.Argument(..., help="Study mode: kana, hiragana, katakana, kanji, keigo, vocab, survival"),
    level: str | None = typer.Option(None, "--level", help="Kanji level (N5, N4, N3, N2)"),
    context: str | None = typer.Option(None, "--context", help="Keigo context (email, meeting, etc.)"),
    count: int = typer.Option(30, "--count", help="Number of questions"),
    db_path: str | None = typer.Option(None, "--db", help="Path to SQLite DB"),
) -> None:
    mode = mode.lower().strip()
    if mode not in {"kana", "hiragana", "katakana", "kanji", "keigo", "vocab", "survival"}:
        print("Mode must be one of: kana, hiragana, katakana, kanji, keigo, vocab, survival")
        raise typer.Exit(code=2)

    if mode == "kanji":
        if not level:
            print("Kanji mode requires --level (N5, N4, N3, N2)")
            raise typer.Exit(code=2)
        level = level.upper()
        if level not in {"N5", "N4", "N3", "N2"}:
            print("Kanji level must be one of: N5, N4, N3, N2")
            raise typer.Exit(code=2)
    else:
        level = None

    paths = resolve_paths(db_path)
    conn = db.connect(paths.db_path)
    db.ensure_schema(conn)

    try:
        verify_vocab_hashes(conn, paths.data_dir, mode, level)
    except Exception as exc:
        print(str(exc))
        raise typer.Exit(code=1)

    vocab = load_vocab_for_mode(paths.data_dir, mode, level)
    seed = int(datetime.now(timezone.utc).timestamp())
    request = StudyRequest(mode=mode, level=level, context=context, count=count, seed=seed)
    llm_config = get_llm_config() if mode == "keigo" else None
    run_quiz(conn, request, vocab, llm_config)


@app.command()
def stats(
    db_path: str | None = typer.Option(None, "--db", help="Path to SQLite DB"),
) -> None:
    paths = resolve_paths(db_path)
    conn = db.connect(paths.db_path)
    db.ensure_schema(conn)

    today_iso = date.today().isoformat()
    overview = db.stats_overview(conn)
    due = db.stats_due(conn, today_iso)

    seven_days_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    thirty_days_ago = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    correct7, total7 = db.stats_accuracy(conn, seven_days_ago)
    correct30, total30 = db.stats_accuracy(conn, thirty_days_ago)

    print(f"Total cards: {overview['total']}")
    print(f"Due cards: {due}")
    if total7:
        print(f"Accuracy (7d): {correct7}/{total7} ({correct7 * 100 // total7}%)")
    else:
        print("Accuracy (7d): no reviews")
    if total30:
        print(f"Accuracy (30d): {correct30}/{total30} ({correct30 * 100 // total30}%)")
    else:
        print("Accuracy (30d): no reviews")

    rows = db.stats_by_mode(conn)
    if rows:
        print("")
        print("By mode:")
        for row in rows:
            print(f"- {row['mode']}: total {row['total']}, due {row['due']}")


if __name__ == "__main__":
    app()
