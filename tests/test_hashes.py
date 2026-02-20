from __future__ import annotations

import json

import pytest

from jp_agent import db
from jp_agent.vocab import EXPECTED_FILES, compute_sha256, verify_vocab_hashes


def test_hash_mismatch_requires_sync(tmp_path, vocab_dir):
    db_path = tmp_path / "test.db"
    conn = db.connect(db_path)
    db.ensure_schema(conn)

    filename = EXPECTED_FILES["hiragana"]
    vocab_path = vocab_dir / filename
    db.upsert_vocab_hash(conn, filename, compute_sha256(vocab_path))

    vocab_path.write_text(json.dumps([{"kana": "a", "romaji": "a"}]), encoding="utf-8")

    with pytest.raises(ValueError):
        verify_vocab_hashes(conn, vocab_dir, "hiragana", None)
