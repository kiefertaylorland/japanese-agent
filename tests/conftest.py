from __future__ import annotations

import json
from pathlib import Path

import pytest

from jp_agent.vocab import EXPECTED_FILES


@pytest.fixture()
def vocab_dir(tmp_path: Path) -> Path:
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    kana_entries = [
        {"kana": "a", "romaji": "a"},
        {"kana": "i", "romaji": "i"},
        {"kana": "u", "romaji": "u"},
    ]
    for key in ("hiragana", "katakana"):
        (data_dir / EXPECTED_FILES[key]).write_text(json.dumps(kana_entries), encoding="utf-8")

    kanji_entries = [
        {"kanji": "日", "meaning": ["sun", "day"]},
        {"kanji": "月", "meaning": ["moon", "month"]},
        {"kanji": "火", "meaning": ["fire"]},
    ]
    for level in ("N5", "N4", "N3", "N2"):
        filename = EXPECTED_FILES[f"kanji_{level}"]
        (data_dir / filename).write_text(json.dumps(kanji_entries), encoding="utf-8")

    keigo_entries = [
        {
            "base": "言う",
            "keigo": "申し上げる",
            "type": "kenjogo",
            "meaning": "to say (humble)",
            "usage": "business",
            "example_contexts": ["email", "meeting"],
        },
        {
            "base": "見る",
            "keigo": "拝見する",
            "type": "kenjogo",
            "meaning": "to see (humble)",
            "usage": "business",
            "example_contexts": ["email"],
        },
        {
            "base": "行く",
            "keigo": "伺う",
            "type": "kenjogo",
            "meaning": "to go (humble)",
            "usage": "business",
            "example_contexts": ["meeting"],
        },
    ]
    (data_dir / EXPECTED_FILES["keigo"]).write_text(json.dumps(keigo_entries), encoding="utf-8")

    return data_dir
