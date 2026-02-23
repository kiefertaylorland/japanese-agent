from __future__ import annotations

from jp_agent.models import CardSpec
from jp_agent.vocab import KanaEntry, KanjiEntry, KeigoEntry, PhraseEntry, VocabStore


def build_kana_cards(mode: str, entries: list[KanaEntry]) -> list[CardSpec]:
    cards: list[CardSpec] = []
    for entry in entries:
        kana = entry.kana
        cards.append(
            CardSpec(
                card_id=f"{mode}:{kana}:kana_to_romaji",
                mode=mode,
                level=None,
                variant="kana_to_romaji",
                vocab_key=kana,
            )
        )
        cards.append(
            CardSpec(
                card_id=f"{mode}:{kana}:romaji_to_kana",
                mode=mode,
                level=None,
                variant="romaji_to_kana",
                vocab_key=kana,
            )
        )
    return cards


def build_kanji_cards(level: str, entries: list[KanjiEntry]) -> list[CardSpec]:
    cards: list[CardSpec] = []
    for entry in entries:
        kanji = entry.kanji
        cards.append(
            CardSpec(
                card_id=f"kanji:{level}:{kanji}:kanji_to_meaning",
                mode="kanji",
                level=level,
                variant="kanji_to_meaning",
                vocab_key=kanji,
            )
        )
        cards.append(
            CardSpec(
                card_id=f"kanji:{level}:{kanji}:meaning_to_kanji",
                mode="kanji",
                level=level,
                variant="meaning_to_kanji",
                vocab_key=kanji,
            )
        )
    return cards


def build_keigo_cards(entries: list[KeigoEntry]) -> list[CardSpec]:
    cards: list[CardSpec] = []
    for entry in entries:
        base = entry.base
        cards.append(
            CardSpec(
                card_id=f"keigo:{base}:plain_to_keigo",
                mode="keigo",
                level=None,
                variant="plain_to_keigo",
                vocab_key=base,
            )
        )
        cards.append(
            CardSpec(
                card_id=f"keigo:{base}:context_selection",
                mode="keigo",
                level=None,
                variant="context_selection",
                vocab_key=base,
            )
        )
        cards.append(
            CardSpec(
                card_id=f"keigo:{base}:politeness_classification",
                mode="keigo",
                level=None,
                variant="politeness_classification",
                vocab_key=base,
            )
        )
    return cards


def build_phrase_cards(mode: str, entries: list[PhraseEntry]) -> list[CardSpec]:
    cards: list[CardSpec] = []
    for entry in entries:
        key = entry.english
        cards.append(
            CardSpec(
                card_id=f"{mode}:{key}:english_to_japanese",
                mode=mode,
                level=None,
                variant="english_to_japanese",
                vocab_key=key,
            )
        )
        cards.append(
            CardSpec(
                card_id=f"{mode}:{key}:japanese_to_english",
                mode=mode,
                level=None,
                variant="japanese_to_english",
                vocab_key=key,
            )
        )
    return cards


def build_all_cards(vocab: VocabStore) -> list[CardSpec]:
    cards: list[CardSpec] = []
    cards.extend(build_kana_cards("hiragana", vocab.hiragana))
    cards.extend(build_kana_cards("katakana", vocab.katakana))
    for level, entries in vocab.kanji.items():
        cards.extend(build_kanji_cards(level, entries))
    cards.extend(build_keigo_cards(vocab.keigo))
    cards.extend(build_phrase_cards("vocab", vocab.core_vocab))
    cards.extend(build_phrase_cards("survival", vocab.survival_phrases))
    return cards


def parse_vocab_key(card_id: str, mode: str) -> str:
    parts = card_id.split(":")
    if mode in {"hiragana", "katakana"}:
        if len(parts) < 3:
            raise ValueError(f"Invalid card_id for kana: {card_id}")
        return parts[1]
    if mode == "kanji":
        if len(parts) < 4:
            raise ValueError(f"Invalid card_id for kanji: {card_id}")
        return parts[2]
    if mode == "keigo":
        if len(parts) < 3:
            raise ValueError(f"Invalid card_id for keigo: {card_id}")
        return parts[1]
    if mode in {"vocab", "survival"}:
        if len(parts) < 3:
            raise ValueError(f"Invalid card_id for {mode}: {card_id}")
        return parts[1]
    raise ValueError(f"Unsupported mode for card_id parse: {mode}")
