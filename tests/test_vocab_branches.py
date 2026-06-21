from __future__ import annotations

import json

import pytest

from jp_agent import db
from jp_agent.vocab import (
    EXPECTED_FILES,
    VocabStore,
    _load_json,
    _normalize_meaning,
    compute_sha256,
    load_all_vocab,
    load_kana,
    load_kanji,
    load_keigo,
    load_phrases,
    load_vocab_for_mode,
    required_filenames,
    resolve_vocab_path,
    verify_vocab_hashes,
)


def test_vocab_store_helpers_and_required_filenames(vocab_dir):
    store = load_all_vocab(vocab_dir)
    assert store.kana_by_mode("hiragana")[0].kana == "a"
    assert store.kana_by_mode("katakana")[0].kana == "a"
    assert store.kanji_by_level("N5")[0].kanji == "日"
    assert required_filenames("kana", None) == [EXPECTED_FILES["hiragana"], EXPECTED_FILES["katakana"]]
    assert required_filenames("hiragana", None) == [EXPECTED_FILES["hiragana"]]
    assert required_filenames("kanji", "N5") == [EXPECTED_FILES["kanji_N5"]]
    assert required_filenames("keigo", None) == [EXPECTED_FILES["keigo"]]
    assert required_filenames("vocab", None) == [EXPECTED_FILES["core_vocab"]]
    assert required_filenames("survival", None) == [EXPECTED_FILES["survival"]]

    with pytest.raises(ValueError, match="Unsupported kana mode"):
        store.kana_by_mode("kana")
    with pytest.raises(ValueError, match="Missing kanji level data"):
        store.kanji_by_level("N1")
    with pytest.raises(ValueError, match="Kanji mode requires level"):
        required_filenames("kanji", None)
    with pytest.raises(ValueError, match="Unsupported mode"):
        required_filenames("other", None)


def test_resolve_vocab_path_and_json_loader(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    no_extension = data_dir / "hiragana"
    no_extension.write_text("[]", encoding="utf-8")
    assert resolve_vocab_path(data_dir, "hiragana.json") == no_extension

    with pytest.raises(FileNotFoundError, match="Missing vocab file"):
        resolve_vocab_path(data_dir, "missing.json")

    bad_json = data_dir / "bad.json"
    bad_json.write_text('{"not": "a list"}', encoding="utf-8")
    with pytest.raises(ValueError, match="JSON array"):
        _load_json(bad_json)
    with pytest.raises(FileNotFoundError, match="Missing vocab file"):
        _load_json(data_dir / "absent.json")


def test_kana_and_kanji_validation_errors(tmp_path):
    kana_path = tmp_path / "kana.json"
    kana_path.write_text(json.dumps(["bad"]), encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid kana entry"):
        load_kana(kana_path)

    kana_path.write_text(json.dumps([{"kana": "a", "romaji": 1}]), encoding="utf-8")
    with pytest.raises(ValueError, match="Kana entries require"):
        load_kana(kana_path)

    assert _normalize_meaning("sun", kana_path, 0) == ["sun"]
    assert _normalize_meaning(["sun", "day"], kana_path, 0) == ["sun", "day"]
    with pytest.raises(ValueError, match="must be string or list of strings"):
        _normalize_meaning(3, kana_path, 0)

    kanji_path = tmp_path / "kanji.json"
    kanji_path.write_text(json.dumps(["bad"]), encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid kanji entry"):
        load_kanji(kanji_path)

    kanji_path.write_text(json.dumps([{"meaning": "sun"}]), encoding="utf-8")
    with pytest.raises(ValueError, match="requires 'kanji' string"):
        load_kanji(kanji_path)


def test_keigo_and_phrase_validation_errors(tmp_path):
    keigo_path = tmp_path / "keigo.json"
    keigo_path.write_text(json.dumps(["bad"]), encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid keigo entry"):
        load_keigo(keigo_path)

    keigo_path.write_text(
        json.dumps(
            [
                {
                    "base": "言う",
                    "keigo": "申し上げる",
                    "type": "kenjogo",
                    "meaning": "to say",
                    "usage": 1,
                    "example_contexts": ["email"],
                }
            ]
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="requires string fields"):
        load_keigo(keigo_path)

    keigo_path.write_text(
        json.dumps(
            [
                {
                    "base": "言う",
                    "keigo": "申し上げる",
                    "type": "kenjogo",
                    "meaning": "to say",
                    "usage": "business",
                    "example_contexts": "email",
                }
            ]
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="must be list of strings"):
        load_keigo(keigo_path)

    phrase_path = tmp_path / "phrases.json"
    phrase_path.write_text(json.dumps(["bad"]), encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid phrase entry"):
        load_phrases(phrase_path)

    phrase_path.write_text(json.dumps([{"english": "a", "japanese": "b", "kana": "c", "romaji": 1}]), encoding="utf-8")
    with pytest.raises(ValueError, match="requires english/japanese/kana/romaji strings"):
        load_phrases(phrase_path)

    phrase_path.write_text(
        json.dumps([{"english": "a", "japanese": "b", "kana": "c", "romaji": "d", "category": 1}]),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="category must be string"):
        load_phrases(phrase_path)

    phrase_path.write_text(
        json.dumps([{"english": "a", "japanese": "b", "kana": "c", "romaji": "d", "note": 1}]),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="note must be string"):
        load_phrases(phrase_path)


def test_load_vocab_for_mode_branches_and_hash_checks(tmp_path, vocab_dir):
    kana = load_vocab_for_mode(vocab_dir, "kana", None)
    assert len(kana.hiragana) == 3
    assert len(kana.katakana) == 3
    assert len(load_vocab_for_mode(vocab_dir, "katakana", None).katakana) == 3
    assert len(load_vocab_for_mode(vocab_dir, "kanji", "N5").kanji["N5"]) == 3
    assert len(load_vocab_for_mode(vocab_dir, "keigo", None).keigo) == 3

    with pytest.raises(ValueError, match="Kanji mode requires a level"):
        load_vocab_for_mode(vocab_dir, "kanji", None)
    with pytest.raises(ValueError, match="Unsupported kanji level"):
        load_vocab_for_mode(vocab_dir, "kanji", "N1")
    with pytest.raises(ValueError, match="Unsupported mode"):
        load_vocab_for_mode(vocab_dir, "other", None)

    conn = db.connect(tmp_path / "hashes.db")
    db.ensure_schema(conn)

    with pytest.raises(ValueError, match="not initialized"):
        verify_vocab_hashes(conn, vocab_dir, "hiragana", None)

    for name in required_filenames("hiragana", None):
        db.upsert_vocab_hash(conn, name, compute_sha256(vocab_dir / name))
    verify_vocab_hashes(conn, vocab_dir, "hiragana", None)
