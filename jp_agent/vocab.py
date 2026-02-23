from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

VALID_KEIGO_TYPES = {"sonkeigo", "kenjogo", "teineigo"}


@dataclass(frozen=True)
class KanaEntry:
    kana: str
    romaji: str


@dataclass(frozen=True)
class KanjiEntry:
    kanji: str
    meaning: list[str]


@dataclass(frozen=True)
class KeigoEntry:
    base: str
    keigo: str
    type: str
    meaning: str
    usage: str
    example_contexts: list[str]


@dataclass(frozen=True)
class PhraseEntry:
    english: str
    japanese: str
    kana: str
    romaji: str
    category: str | None = None
    note: str | None = None


@dataclass
class VocabStore:
    hiragana: list[KanaEntry]
    katakana: list[KanaEntry]
    kanji: dict[str, list[KanjiEntry]]
    keigo: list[KeigoEntry]
    core_vocab: list[PhraseEntry]
    survival_phrases: list[PhraseEntry]

    def kana_by_mode(self, mode: str) -> list[KanaEntry]:
        if mode == "hiragana":
            return self.hiragana
        if mode == "katakana":
            return self.katakana
        raise ValueError(f"Unsupported kana mode: {mode}")

    def kanji_by_level(self, level: str) -> list[KanjiEntry]:
        if level not in self.kanji:
            raise ValueError(f"Missing kanji level data: {level}")
        return self.kanji[level]


EXPECTED_FILES = {
    "hiragana": "hiragana.json",
    "katakana": "katakana.json",
    "keigo": "keigo_basic.json",
    "core_vocab": "core_vocab_survival.json",
    "survival": "survival_phrases.json",
    "kanji_N5": "kanji_N5.json",
    "kanji_N4": "kanji_N4.json",
    "kanji_N3": "kanji_N3.json",
    "kanji_N2": "kanji_N2.json",
}


def resolve_vocab_path(data_dir: Path, filename: str) -> Path:
    candidates = [data_dir / filename, data_dir / filename.lower()]
    if filename.lower().endswith(".json"):
        stem = filename[:-5]
        candidates.append(data_dir / stem)
        candidates.append(data_dir / stem.lower())
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"Missing vocab file: {data_dir / filename}")


def required_filenames(mode: str, level: str | None) -> list[str]:
    if mode == "kana":
        return [EXPECTED_FILES["hiragana"], EXPECTED_FILES["katakana"]]
    if mode in {"hiragana", "katakana"}:
        return [EXPECTED_FILES[mode]]
    if mode == "kanji":
        if not level:
            raise ValueError("Kanji mode requires level")
        return [EXPECTED_FILES[f"kanji_{level}"]]
    if mode == "keigo":
        return [EXPECTED_FILES["keigo"]]
    if mode == "vocab":
        return [EXPECTED_FILES["core_vocab"]]
    if mode == "survival":
        return [EXPECTED_FILES["survival"]]
    if mode == "vocab":
        entries = load_phrases(resolve_vocab_path(data_dir, EXPECTED_FILES["core_vocab"]))
        return VocabStore(hiragana=[], katakana=[], kanji={}, keigo=[], core_vocab=entries, survival_phrases=[])
    if mode == "survival":
        entries = load_phrases(resolve_vocab_path(data_dir, EXPECTED_FILES["survival"]))
        return VocabStore(hiragana=[], katakana=[], kanji={}, keigo=[], core_vocab=[], survival_phrases=entries)
    raise ValueError(f"Unsupported mode: {mode}")


def verify_vocab_hashes(conn, data_dir: Path, mode: str, level: str | None) -> None:
    from jp_agent import db

    for filename in required_filenames(mode, level):
        vocab_path = resolve_vocab_path(data_dir, filename)
        current_hash = compute_sha256(vocab_path)
        stored_hash = db.get_vocab_hash(conn, filename)
        if stored_hash is None:
            raise ValueError("Vocab hashes not initialized. Run 'jp-agent init --sync'.")
        if current_hash != stored_hash:
            raise ValueError("Vocab file hash mismatch. Run 'jp-agent init --sync'.")


def compute_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"Missing vocab file: {path}")
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError(f"Vocab file must be a JSON array: {path}")
    return data


def load_kana(path: Path) -> list[KanaEntry]:
    raw = _load_json(path)
    entries: list[KanaEntry] = []
    for idx, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"Invalid kana entry at index {idx} in {path}")
        kana = item.get("kana")
        romaji = item.get("romaji")
        if not isinstance(kana, str) or not isinstance(romaji, str):
            raise ValueError(f"Kana entries require 'kana' and 'romaji' strings at index {idx} in {path}")
        entries.append(KanaEntry(kana=kana, romaji=romaji))
    return entries


def _normalize_meaning(value: object, path: Path, idx: int) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return list(value)
    raise ValueError(f"Kanji entry 'meaning' must be string or list of strings at index {idx} in {path}")


def load_kanji(path: Path) -> list[KanjiEntry]:
    raw = _load_json(path)
    entries: list[KanjiEntry] = []
    for idx, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"Invalid kanji entry at index {idx} in {path}")
        kanji = item.get("kanji")
        meaning = item.get("meaning")
        if not isinstance(kanji, str):
            raise ValueError(f"Kanji entry requires 'kanji' string at index {idx} in {path}")
        entries.append(KanjiEntry(kanji=kanji, meaning=_normalize_meaning(meaning, path, idx)))
    return entries


def load_keigo(path: Path) -> list[KeigoEntry]:
    raw = _load_json(path)
    entries: list[KeigoEntry] = []
    for idx, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"Invalid keigo entry at index {idx} in {path}")
        base = item.get("base")
        keigo = item.get("keigo")
        ktype = item.get("type")
        meaning = item.get("meaning")
        usage = item.get("usage")
        contexts = item.get("example_contexts")
        if not all(isinstance(val, str) for val in (base, keigo, ktype, meaning, usage)):
            raise ValueError(f"Keigo entry requires string fields at index {idx} in {path}")
        if ktype not in VALID_KEIGO_TYPES:
            raise ValueError(f"Keigo entry 'type' must be one of {sorted(VALID_KEIGO_TYPES)} at index {idx} in {path}")
        if not isinstance(contexts, list) or not all(isinstance(val, str) for val in contexts):
            raise ValueError(f"Keigo entry 'example_contexts' must be list of strings at index {idx} in {path}")
        entries.append(
            KeigoEntry(
                base=base,
                keigo=keigo,
                type=ktype,
                meaning=meaning,
                usage=usage,
                example_contexts=list(contexts),
            )
        )
    return entries




def load_phrases(path: Path) -> list[PhraseEntry]:
    raw = _load_json(path)
    entries: list[PhraseEntry] = []
    for idx, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"Invalid phrase entry at index {idx} in {path}")
        english = item.get("english")
        japanese = item.get("japanese")
        kana = item.get("kana")
        romaji = item.get("romaji")
        if not all(isinstance(val, str) for val in (english, japanese, kana, romaji)):
            raise ValueError(f"Phrase entry requires english/japanese/kana/romaji strings at index {idx} in {path}")
        category = item.get("category")
        note = item.get("note")
        if category is not None and not isinstance(category, str):
            raise ValueError(f"Phrase entry category must be string at index {idx} in {path}")
        if note is not None and not isinstance(note, str):
            raise ValueError(f"Phrase entry note must be string at index {idx} in {path}")
        entries.append(PhraseEntry(english=english, japanese=japanese, kana=kana, romaji=romaji, category=category, note=note))
    return entries

def load_all_vocab(data_dir: Path) -> VocabStore:
    hiragana = load_kana(resolve_vocab_path(data_dir, EXPECTED_FILES["hiragana"]))
    katakana = load_kana(resolve_vocab_path(data_dir, EXPECTED_FILES["katakana"]))
    kanji = {
        "N5": load_kanji(resolve_vocab_path(data_dir, EXPECTED_FILES["kanji_N5"])),
        "N4": load_kanji(resolve_vocab_path(data_dir, EXPECTED_FILES["kanji_N4"])),
        "N3": load_kanji(resolve_vocab_path(data_dir, EXPECTED_FILES["kanji_N3"])),
        "N2": load_kanji(resolve_vocab_path(data_dir, EXPECTED_FILES["kanji_N2"])),
    }
    keigo = load_keigo(resolve_vocab_path(data_dir, EXPECTED_FILES["keigo"]))
    core_vocab = load_phrases(resolve_vocab_path(data_dir, EXPECTED_FILES["core_vocab"]))
    survival_phrases = load_phrases(resolve_vocab_path(data_dir, EXPECTED_FILES["survival"]))
    return VocabStore(
        hiragana=hiragana,
        katakana=katakana,
        kanji=kanji,
        keigo=keigo,
        core_vocab=core_vocab,
        survival_phrases=survival_phrases,
    )


def load_vocab_for_mode(data_dir: Path, mode: str, level: str | None) -> VocabStore:
    if mode == "kana":
        hiragana = load_kana(resolve_vocab_path(data_dir, EXPECTED_FILES["hiragana"]))
        katakana = load_kana(resolve_vocab_path(data_dir, EXPECTED_FILES["katakana"]))
        return VocabStore(hiragana=hiragana, katakana=katakana, kanji={}, keigo=[], core_vocab=[], survival_phrases=[])
    if mode in {"hiragana", "katakana"}:
        hiragana = (
            load_kana(resolve_vocab_path(data_dir, EXPECTED_FILES["hiragana"])) if mode == "hiragana" else []
        )
        katakana = (
            load_kana(resolve_vocab_path(data_dir, EXPECTED_FILES["katakana"])) if mode == "katakana" else []
        )
        return VocabStore(hiragana=hiragana, katakana=katakana, kanji={}, keigo=[], core_vocab=[], survival_phrases=[])
    if mode == "kanji":
        if not level:
            raise ValueError("Kanji mode requires a level (N5, N4, N3, N2)")
        filename = EXPECTED_FILES.get(f"kanji_{level}")
        if not filename:
            raise ValueError(f"Unsupported kanji level: {level}")
        kanji_entries = load_kanji(resolve_vocab_path(data_dir, filename))
        return VocabStore(hiragana=[], katakana=[], kanji={level: kanji_entries}, keigo=[], core_vocab=[], survival_phrases=[])
    if mode == "keigo":
        keigo = load_keigo(resolve_vocab_path(data_dir, EXPECTED_FILES["keigo"]))
        return VocabStore(hiragana=[], katakana=[], kanji={}, keigo=keigo, core_vocab=[], survival_phrases=[])
    if mode == "vocab":
        entries = load_phrases(resolve_vocab_path(data_dir, EXPECTED_FILES["core_vocab"]))
        return VocabStore(hiragana=[], katakana=[], kanji={}, keigo=[], core_vocab=entries, survival_phrases=[])
    if mode == "survival":
        entries = load_phrases(resolve_vocab_path(data_dir, EXPECTED_FILES["survival"]))
        return VocabStore(hiragana=[], katakana=[], kanji={}, keigo=[], core_vocab=[], survival_phrases=entries)
    raise ValueError(f"Unsupported mode: {mode}")
