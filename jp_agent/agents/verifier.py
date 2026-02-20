from __future__ import annotations

import re
from dataclasses import dataclass

from jp_agent.models import CardSpec, GeneratedQuestion, VerifiedQuestion
from jp_agent.vocab import VocabStore

_JP_CHAR_RE = re.compile(r"[\u3040-\u30ff\u4e00-\u9fff]")


class VerifierAgent:
    def verify(self, card: CardSpec, question: GeneratedQuestion, vocab: VocabStore) -> VerifiedQuestion:
        issues: list[str] = []
        if question.correct_index < 0 or question.correct_index >= len(question.choices):
            issues.append("correct_index out of range")
        if len(question.choices) != len(set(question.choices)):
            issues.append("duplicate choices")

        if card.mode in {"hiragana", "katakana"}:
            self._verify_kana(card, question, vocab, issues)
        elif card.mode == "kanji":
            self._verify_kanji(card, question, vocab, issues)
        elif card.mode == "keigo":
            self._verify_keigo(card, question, vocab, issues)
        else:
            issues.append(f"unsupported mode: {card.mode}")

        return VerifiedQuestion(valid=not issues, question=question, issues=issues)

    def _verify_kana(self, card: CardSpec, question: GeneratedQuestion, vocab: VocabStore, issues: list[str]) -> None:
        entries = vocab.kana_by_mode(card.mode)
        kana_set = {entry.kana for entry in entries}
        romaji_set = {entry.romaji for entry in entries}
        if card.variant == "kana_to_romaji":
            if any(choice not in romaji_set for choice in question.choices):
                issues.append("kana_to_romaji choices not in whitelist")
        elif card.variant == "romaji_to_kana":
            if any(choice not in kana_set for choice in question.choices):
                issues.append("romaji_to_kana choices not in whitelist")
        else:
            issues.append("unknown kana variant")

    def _verify_kanji(self, card: CardSpec, question: GeneratedQuestion, vocab: VocabStore, issues: list[str]) -> None:
        if not card.level:
            issues.append("kanji card missing level")
            return
        entries = vocab.kanji_by_level(card.level)
        kanji_set = {entry.kanji for entry in entries}
        meaning_set = {meaning for entry in entries for meaning in entry.meaning}
        if card.variant == "kanji_to_meaning":
            if any(choice not in meaning_set for choice in question.choices):
                issues.append("kanji_to_meaning choices not in whitelist")
        elif card.variant == "meaning_to_kanji":
            if any(choice not in kanji_set for choice in question.choices):
                issues.append("meaning_to_kanji choices not in whitelist")
        else:
            issues.append("unknown kanji variant")

    def _verify_keigo(self, card: CardSpec, question: GeneratedQuestion, vocab: VocabStore, issues: list[str]) -> None:
        keigo_entries = vocab.keigo
        base_map = {entry.base: entry for entry in keigo_entries}
        keigo_set = {entry.keigo for entry in keigo_entries}
        if card.vocab_key not in base_map:
            issues.append("keigo base missing in whitelist")
            return
        entry = base_map[card.vocab_key]
        if card.variant in {"plain_to_keigo", "context_selection"}:
            if any(choice not in keigo_set for choice in question.choices):
                issues.append("keigo choices not in whitelist")
            if question.choices[question.correct_index] != entry.keigo:
                issues.append("keigo correct answer mismatch")
        elif card.variant == "politeness_classification":
            expected = {"Sonkeigo", "Kenjogo", "Teineigo"}
            if set(question.choices) != expected:
                issues.append("keigo classification choices invalid")
            mapping = {"sonkeigo": "Sonkeigo", "kenjogo": "Kenjogo", "teineigo": "Teineigo"}
            if question.choices[question.correct_index] != mapping[entry.type]:
                issues.append("keigo classification correct mismatch")
        else:
            issues.append("unknown keigo variant")

        self._verify_explanation(entry, question, issues)

    def _verify_explanation(self, entry, question: GeneratedQuestion, issues: list[str]) -> None:
        if not question.explanation:
            return
        japanese_chars = _JP_CHAR_RE.findall(question.explanation)
        if not japanese_chars:
            return
        allowed_chars = set(entry.base + entry.keigo)
        for ch in japanese_chars:
            if ch not in allowed_chars:
                issues.append("explanation includes non-whitelisted Japanese text")
                break
