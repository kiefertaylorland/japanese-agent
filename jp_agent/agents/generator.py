from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Sequence

from jp_agent.llm import LlmConfig
from jp_agent.models import CardSpec, GeneratedQuestion, StudyRequest
from jp_agent.vocab import KanaEntry, KanjiEntry, KeigoEntry, VocabStore


@dataclass
class _KeigoPrompt:
    prompt: str
    choices: list[str]
    correct_index: int


class ContentGeneratorAgent:
    def __init__(self, vocab: VocabStore, llm: LlmConfig | None = None) -> None:
        self.vocab = vocab
        self.llm = llm
        self._last_llm_call = 0.0
        self._kana_maps = {
            "hiragana": {entry.kana: entry for entry in vocab.hiragana},
            "katakana": {entry.kana: entry for entry in vocab.katakana},
        }
        self._kanji_maps = {level: {entry.kanji: entry for entry in entries} for level, entries in vocab.kanji.items()}
        self._keigo_map = {entry.base: entry for entry in vocab.keigo}

    def generate(
        self,
        card: CardSpec,
        request: StudyRequest,
        rng: random.Random,
        use_llm: bool = True,
    ) -> GeneratedQuestion:
        if card.mode in {"hiragana", "katakana"}:
            return self._generate_kana(card, rng)
        if card.mode == "kanji":
            return self._generate_kanji(card, rng)
        if card.mode == "keigo":
            return self._generate_keigo(card, request, rng, use_llm=use_llm)
        raise ValueError(f"Unsupported mode: {card.mode}")

    def _generate_kana(self, card: CardSpec, rng: random.Random) -> GeneratedQuestion:
        entries = self.vocab.kana_by_mode(card.mode)
        if len(entries) < 3:
            raise ValueError(f"Not enough {card.mode} entries for MCQ (need 3)")
        entry_map = self._kana_maps[card.mode]
        entry = entry_map[card.vocab_key]
        if card.variant == "kana_to_romaji":
            prompt = f"{entry.kana} -> ?"
            pool = [item.romaji for item in entries]
            correct = entry.romaji
        elif card.variant == "romaji_to_kana":
            prompt = f"{entry.romaji} -> ?"
            pool = [item.kana for item in entries]
            correct = entry.kana
        else:
            raise ValueError(f"Unsupported kana variant: {card.variant}")
        choices, correct_index = _build_choices(rng, pool, correct)
        return GeneratedQuestion(
            prompt=prompt,
            choices=choices,
            correct_index=correct_index,
            explanation="",
            meta={"mode": card.mode, "variant": card.variant},
        )

    def _generate_kanji(self, card: CardSpec, rng: random.Random) -> GeneratedQuestion:
        if card.level is None:
            raise ValueError("Kanji card missing level")
        entries = self.vocab.kanji_by_level(card.level)
        if len(entries) < 3:
            raise ValueError(f"Not enough kanji entries for MCQ (need 3) in {card.level}")
        entry_map = self._kanji_maps[card.level]
        entry = entry_map[card.vocab_key]
        if card.variant == "kanji_to_meaning":
            meaning = rng.choice(entry.meaning)
            prompt = f"{entry.kanji} -> ?"
            pool = [_random_meaning(rng, item) for item in entries]
            correct = meaning
        elif card.variant == "meaning_to_kanji":
            meaning = rng.choice(entry.meaning)
            prompt = f"{meaning} -> ?"
            pool = [item.kanji for item in entries]
            correct = entry.kanji
        else:
            raise ValueError(f"Unsupported kanji variant: {card.variant}")
        choices, correct_index = _build_choices(rng, pool, correct)
        return GeneratedQuestion(
            prompt=prompt,
            choices=choices,
            correct_index=correct_index,
            explanation="",
            meta={"mode": card.mode, "variant": card.variant, "level": card.level},
        )

    def _generate_keigo(
        self,
        card: CardSpec,
        request: StudyRequest,
        rng: random.Random,
        use_llm: bool,
    ) -> GeneratedQuestion:
        if len(self.vocab.keigo) < 3 and card.variant != "politeness_classification":
            raise ValueError("Not enough keigo entries for MCQ (need 3)")
        entry = self._keigo_map[card.vocab_key]
        prompt_data = self._keigo_prompt(card, entry, request, rng)
        explanation = self._keigo_explanation(entry, request.context, use_llm=use_llm)
        return GeneratedQuestion(
            prompt=prompt_data.prompt,
            choices=prompt_data.choices,
            correct_index=prompt_data.correct_index,
            explanation=explanation,
            meta={
                "mode": card.mode,
                "variant": card.variant,
                "type": entry.type,
                "usage": entry.usage,
                "base": entry.base,
                "keigo": entry.keigo,
            },
        )

    def _keigo_prompt(
        self,
        card: CardSpec,
        entry: KeigoEntry,
        request: StudyRequest,
        rng: random.Random,
    ) -> _KeigoPrompt:
        if card.variant == "plain_to_keigo":
            prompt = f"{entry.base} -> ?"
            pool = [item.keigo for item in self.vocab.keigo]
            choices, correct_index = _build_choices(rng, pool, entry.keigo)
            return _KeigoPrompt(prompt=prompt, choices=choices, correct_index=correct_index)

        if card.variant == "context_selection":
            context = request.context if request.context in entry.example_contexts else entry.example_contexts[0]
            prompt = f"Which is appropriate in a {context} context?"
            pool_entries = [item for item in self.vocab.keigo if item.base != entry.base]
            if request.context:
                filtered = [item for item in pool_entries if request.context not in item.example_contexts]
                if len(filtered) >= 2:
                    pool_entries = filtered
            pool = [item.keigo for item in pool_entries] + [entry.keigo]
            choices, correct_index = _build_choices(rng, pool, entry.keigo)
            return _KeigoPrompt(prompt=prompt, choices=choices, correct_index=correct_index)

        if card.variant == "politeness_classification":
            prompt = f"{entry.keigo} is which politeness level?"
            choices = ["Sonkeigo", "Kenjogo", "Teineigo"]
            mapping = {"sonkeigo": 0, "kenjogo": 1, "teineigo": 2}
            correct_index = mapping[entry.type]
            return _KeigoPrompt(prompt=prompt, choices=choices, correct_index=correct_index)

        raise ValueError(f"Unsupported keigo variant: {card.variant}")

    def _keigo_explanation(self, entry: KeigoEntry, context: str | None, use_llm: bool) -> str:
        template = (
            f"{entry.keigo} is the {entry.type} form of {entry.base}. "
            f"Meaning: {entry.meaning}. Usage: {entry.usage}."
        )
        if not use_llm or not self.llm:
            return template

        prompt_context = context or "general business"
        system = (
            "You are a Japanese language tutor. "
            "Explain in English using 2 short sentences. "
            "Do not introduce any Japanese words besides the provided base and keigo terms."
        )
        user = (
            f"Base: {entry.base}\n"
            f"Keigo: {entry.keigo}\n"
            f"Type: {entry.type}\n"
            f"Meaning: {entry.meaning}\n"
            f"Usage: {entry.usage}\n"
            f"Context: {prompt_context}\n"
            "Explain the nuance for business usage."
        )
        self._rate_limit()
        response = self.llm.client.chat.completions.create(
            model=self.llm.model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.2,
            max_tokens=120,
        )
        content = response.choices[0].message.content or ""
        return content.strip() or template

    def _rate_limit(self) -> None:
        now = time.monotonic()
        delta = now - self._last_llm_call
        if delta < 1.0:
            time.sleep(1.0 - delta)
        self._last_llm_call = time.monotonic()


def _build_choices(rng: random.Random, pool: Sequence[str], correct: str) -> tuple[list[str], int]:
    unique_pool = list(dict.fromkeys(pool))
    if correct not in unique_pool:
        unique_pool.append(correct)
    distractors = [item for item in unique_pool if item != correct]
    if len(distractors) < 2:
        raise ValueError("Not enough distractors to build MCQ")
    selected = rng.sample(distractors, 2)
    choices = selected + [correct]
    rng.shuffle(choices)
    correct_index = choices.index(correct)
    return choices, correct_index


def _random_meaning(rng: random.Random, entry: KanjiEntry) -> str:
    return rng.choice(entry.meaning)
