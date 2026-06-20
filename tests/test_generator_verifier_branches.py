from __future__ import annotations

import random
from types import SimpleNamespace

import pytest

from jp_agent.agents import generator as generator_module
from jp_agent.agents.generator import ContentGeneratorAgent
from jp_agent.agents.verifier import VerifierAgent
from jp_agent.llm import LlmConfig
from jp_agent.models import CardSpec, GeneratedQuestion, StudyRequest
from jp_agent.vocab import KanaEntry, KanjiEntry, KeigoEntry, PhraseEntry, VocabStore, load_all_vocab


def _request(mode: str, *, context: str | None = None) -> StudyRequest:
    return StudyRequest(mode=mode, level="N5" if mode == "kanji" else None, context=context, count=1, seed=7)


def test_generator_covers_kanji_phrase_and_keigo_modes(vocab_dir):
    vocab = load_all_vocab(vocab_dir)
    generator = ContentGeneratorAgent(vocab=vocab, llm=None)

    kana_card = CardSpec("hiragana:a:romaji_to_kana", "hiragana", None, "romaji_to_kana", "a")
    kana_question = generator.generate(kana_card, _request("hiragana"), random.Random(5))
    assert kana_question.prompt == "a -> ?"
    assert kana_question.choices[kana_question.correct_index] == "a"

    kana_to_meaning = CardSpec("kanji:N5:日:kanji_to_meaning", "kanji", "N5", "kanji_to_meaning", "日")
    kanji_card = CardSpec("kanji:N5:日:meaning_to_kanji", "kanji", "N5", "meaning_to_kanji", "日")
    phrase_card = CardSpec("vocab:friend:japanese_to_english", "vocab", None, "japanese_to_english", "friend")
    keigo_card = CardSpec("keigo:言う:plain_to_keigo", "keigo", None, "plain_to_keigo", "言う")
    context_card = CardSpec("keigo:見る:context_selection", "keigo", None, "context_selection", "見る")

    meaning_question = generator.generate(kana_to_meaning, _request("kanji"), random.Random(1))
    assert meaning_question.prompt == "日 -> ?"
    assert meaning_question.choices[meaning_question.correct_index] in {"sun", "day"}

    kanji_question = generator.generate(kanji_card, _request("kanji"), random.Random(1))
    assert kanji_question.prompt.endswith("-> ?")
    assert kanji_question.choices[kanji_question.correct_index] == "日"

    phrase_question = generator.generate(phrase_card, _request("vocab"), random.Random(2))
    assert phrase_question.choices[phrase_question.correct_index] == "friend"
    assert "Category: people" in phrase_question.explanation

    keigo_question = generator.generate(keigo_card, _request("keigo"), random.Random(3))
    assert keigo_question.choices[keigo_question.correct_index] == "申し上げる"

    context_question = generator.generate(context_card, _request("keigo", context="meeting"), random.Random(4))
    assert context_question.prompt == "Which is appropriate in an email context?"
    assert context_question.choices[context_question.correct_index] == "拝見する"


def test_generator_error_paths_and_helpers(monkeypatch):
    sparse_vocab = VocabStore(
        hiragana=[KanaEntry("a", "a"), KanaEntry("i", "i")],
        katakana=[KanaEntry("ア", "a"), KanaEntry("イ", "i")],
        kanji={"N5": [KanjiEntry("日", ["sun"]), KanjiEntry("月", ["moon"])]},
        keigo=[
            KeigoEntry("言う", "申し上げる", "kenjogo", "to say", "business", ["email"]),
            KeigoEntry("見る", "拝見する", "kenjogo", "to see", "business", ["email"]),
        ],
        core_vocab=[PhraseEntry("friend", "友達", "ともだち", "tomodachi"), PhraseEntry("water", "水", "みず", "mizu")],
        survival_phrases=[PhraseEntry("thanks", "ありがとう", "ありがとう", "arigatou"), PhraseEntry("hello", "こんにちは", "こんにちは", "konnichiwa")],
    )
    generator = ContentGeneratorAgent(vocab=sparse_vocab, llm=None)

    with pytest.raises(ValueError, match="Not enough hiragana entries"):
        generator.generate(
            CardSpec("hiragana:a:kana_to_romaji", "hiragana", None, "kana_to_romaji", "a"),
            _request("hiragana"),
            random.Random(1),
        )
    with pytest.raises(ValueError, match="Unsupported mode"):
        generator.generate(CardSpec("other:x:y", "other", None, "y", "x"), _request("hiragana"), random.Random(1))
    with pytest.raises(ValueError, match="Kanji card missing level"):
        generator._generate_kanji(CardSpec("kanji:日:kanji_to_meaning", "kanji", None, "kanji_to_meaning", "日"), random.Random(1))
    with pytest.raises(ValueError, match="Not enough kanji entries"):
        generator._generate_kanji(
            CardSpec("kanji:N5:日:kanji_to_meaning", "kanji", "N5", "kanji_to_meaning", "日"),
            random.Random(1),
        )
    with pytest.raises(ValueError, match="Not enough vocab entries"):
        generator._generate_phrase(
            CardSpec("vocab:friend:english_to_japanese", "vocab", None, "english_to_japanese", "friend"),
            random.Random(1),
            sparse_vocab.core_vocab,
            {"friend": sparse_vocab.core_vocab[0], "water": sparse_vocab.core_vocab[1]},
        )
    with pytest.raises(ValueError, match="Unsupported vocab variant"):
        generator._generate_phrase(
            CardSpec("vocab:friend:bad", "vocab", None, "bad", "friend"),
            random.Random(1),
            sparse_vocab.core_vocab + [PhraseEntry("station", "駅", "えき", "eki")],
            {
                "friend": sparse_vocab.core_vocab[0],
                "water": sparse_vocab.core_vocab[1],
                "station": PhraseEntry("station", "駅", "えき", "eki"),
            },
        )
    with pytest.raises(ValueError, match="Not enough keigo entries"):
        generator._generate_keigo(
            CardSpec("keigo:言う:plain_to_keigo", "keigo", None, "plain_to_keigo", "言う"),
            _request("keigo"),
            random.Random(1),
            True,
        )
    with pytest.raises(ValueError, match="Unsupported keigo variant"):
        generator._keigo_prompt(
            CardSpec("keigo:言う:bad", "keigo", None, "bad", "言う"),
            sparse_vocab.keigo[0],
            _request("keigo"),
            random.Random(1),
        )

    full_vocab = VocabStore(
        hiragana=[KanaEntry("a", "a"), KanaEntry("i", "i"), KanaEntry("u", "u")],
        katakana=[KanaEntry("ア", "a"), KanaEntry("イ", "i"), KanaEntry("ウ", "u")],
        kanji={"N5": [KanjiEntry("日", ["sun"]), KanjiEntry("月", ["moon"]), KanjiEntry("火", ["fire"])]},
        keigo=[
            KeigoEntry("言う", "申し上げる", "kenjogo", "to say", "business", ["email"]),
            KeigoEntry("見る", "拝見する", "kenjogo", "to see", "business", ["meeting"]),
            KeigoEntry("行く", "伺う", "kenjogo", "to go", "business", ["email"]),
        ],
        core_vocab=[
            PhraseEntry("friend", "友達", "ともだち", "tomodachi"),
            PhraseEntry("water", "水", "みず", "mizu"),
            PhraseEntry("station", "駅", "えき", "eki", note="common"),
        ],
        survival_phrases=[
            PhraseEntry("thanks", "ありがとう", "ありがとう", "arigatou"),
            PhraseEntry("hello", "こんにちは", "こんにちは", "konnichiwa"),
            PhraseEntry("bye", "さようなら", "さようなら", "sayounara"),
        ],
    )
    generator = ContentGeneratorAgent(vocab=full_vocab, llm=None)
    with pytest.raises(ValueError, match="Unsupported kana variant"):
        generator._generate_kana(CardSpec("hiragana:a:bad", "hiragana", None, "bad", "a"), random.Random(1))
    with pytest.raises(ValueError, match="Unsupported kanji variant"):
        generator._generate_kanji(
            CardSpec("kanji:N5:日:bad", "kanji", "N5", "bad", "日"),
            random.Random(1),
        )
    phrase = generator.generate(
        CardSpec("vocab:station:english_to_japanese", "vocab", None, "english_to_japanese", "station"),
        _request("vocab"),
        random.Random(1),
    )
    assert "Note: common" in phrase.explanation

    choices, correct_index = generator_module._build_choices(random.Random(1), ["x", "y"], "z")
    assert choices[correct_index] == "z"
    with pytest.raises(ValueError, match="Not enough distractors"):
        generator_module._build_choices(random.Random(1), ["z"], "z")
    assert generator_module._random_meaning(random.Random(1), KanjiEntry("日", ["sun", "day"])) in {"sun", "day"}

    sleep_calls: list[float] = []
    times = iter([10.0, 10.2, 10.9, 11.0])
    monkeypatch.setattr(generator_module.time, "monotonic", lambda: next(times))
    monkeypatch.setattr(generator_module.time, "sleep", lambda seconds: sleep_calls.append(seconds))
    generator._rate_limit()
    generator._rate_limit()
    assert sleep_calls == pytest.approx([0.3])

    filtered_vocab = VocabStore(
        hiragana=[],
        katakana=[],
        kanji={},
        keigo=[
            KeigoEntry("言う", "申し上げる", "kenjogo", "to say", "business", ["email"]),
            KeigoEntry("見る", "拝見する", "kenjogo", "to see", "business", ["meeting"]),
            KeigoEntry("行く", "伺う", "kenjogo", "to go", "business", ["email"]),
            KeigoEntry("来る", "参る", "kenjogo", "to come", "business", ["meeting"]),
        ],
        core_vocab=[],
        survival_phrases=[],
    )
    filtered_generator = ContentGeneratorAgent(vocab=filtered_vocab, llm=None)
    captured_pool: list[str] = []

    def fake_build_choices(rng, pool, correct):
        captured_pool.extend(pool)
        return [correct, pool[0], pool[1]], 0

    monkeypatch.setattr(generator_module, "_build_choices", fake_build_choices)
    filtered_generator._keigo_prompt(
        CardSpec("keigo:見る:context_selection", "keigo", None, "context_selection", "見る"),
        filtered_vocab.keigo[1],
        _request("keigo", context="meeting"),
        random.Random(1),
    )
    assert captured_pool == ["申し上げる", "伺う", "拝見する"]


def test_generator_llm_explanation_uses_template_and_fallback():
    class FakeCompletions:
        def __init__(self, content: str) -> None:
            self._content = content

        def create(self, **kwargs):
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=self._content))]
            )

    entry = KeigoEntry("言う", "申し上げる", "kenjogo", "to say", "business", ["email"])
    vocab = VocabStore(hiragana=[], katakana=[], kanji={}, keigo=[entry], core_vocab=[], survival_phrases=[])

    llm = LlmConfig(client=SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions("  concise  "))), model="gpt")
    generator = ContentGeneratorAgent(vocab=vocab, llm=llm)
    assert generator._keigo_explanation(entry, "email", use_llm=True) == "concise"

    blank_llm = LlmConfig(client=SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions("   "))), model="gpt")
    blank_generator = ContentGeneratorAgent(vocab=vocab, llm=blank_llm)
    explanation = blank_generator._keigo_explanation(entry, None, use_llm=True)
    assert "general business" not in explanation
    assert "申し上げる is the kenjogo form of 言う." in explanation

    assert blank_generator._keigo_explanation(entry, None, use_llm=False).startswith("申し上げる")


def test_verifier_covers_invalid_paths(vocab_dir):
    vocab = load_all_vocab(vocab_dir)
    verifier = VerifierAgent()

    bad_index = GeneratedQuestion("?", ["a", "b"], 3, "", {})
    result = verifier.verify(CardSpec("other:x:y", "other", None, "x", "x"), bad_index, vocab)
    assert not result.valid
    assert "correct_index out of range" in result.issues
    assert "unsupported mode: other" in result.issues

    kana = verifier.verify(
        CardSpec("hiragana:a:romaji_to_kana", "hiragana", None, "romaji_to_kana", "a"),
        GeneratedQuestion("?", ["x", "x"], 0, "", {}),
        vocab,
    )
    assert "duplicate choices" in kana.issues
    assert "romaji_to_kana choices not in whitelist" in kana.issues

    kana_to_romaji = verifier.verify(
        CardSpec("hiragana:a:kana_to_romaji", "hiragana", None, "kana_to_romaji", "a"),
        GeneratedQuestion("?", ["x", "y", "z"], 0, "", {}),
        vocab,
    )
    assert "kana_to_romaji choices not in whitelist" in kana_to_romaji.issues

    unknown_kana = verifier.verify(
        CardSpec("hiragana:a:bad", "hiragana", None, "bad", "a"),
        GeneratedQuestion("?", ["a", "i", "u"], 0, "", {}),
        vocab,
    )
    assert "unknown kana variant" in unknown_kana.issues

    missing_level = verifier.verify(
        CardSpec("kanji:日:kanji_to_meaning", "kanji", None, "kanji_to_meaning", "日"),
        GeneratedQuestion("?", ["sun", "moon", "fire"], 0, "", {}),
        vocab,
    )
    assert missing_level.issues == ["kanji card missing level"]

    bad_kanji = verifier.verify(
        CardSpec("kanji:N5:日:meaning_to_kanji", "kanji", "N5", "meaning_to_kanji", "日"),
        GeneratedQuestion("?", ["X", "Y", "Z"], 0, "", {}),
        vocab,
    )
    assert "meaning_to_kanji choices not in whitelist" in bad_kanji.issues

    bad_kanji_meaning = verifier.verify(
        CardSpec("kanji:N5:日:kanji_to_meaning", "kanji", "N5", "kanji_to_meaning", "日"),
        GeneratedQuestion("?", ["X", "Y", "Z"], 0, "", {}),
        vocab,
    )
    assert "kanji_to_meaning choices not in whitelist" in bad_kanji_meaning.issues

    unknown_kanji = verifier.verify(
        CardSpec("kanji:N5:日:bad", "kanji", "N5", "bad", "日"),
        GeneratedQuestion("?", ["sun", "moon", "fire"], 0, "", {}),
        vocab,
    )
    assert "unknown kanji variant" in unknown_kanji.issues

    missing_phrase = verifier.verify(
        CardSpec("vocab:missing:english_to_japanese", "vocab", None, "english_to_japanese", "missing"),
        GeneratedQuestion("?", ["友達", "駅", "水"], 0, "", {}),
        vocab,
    )
    assert "vocab key missing in whitelist" in missing_phrase.issues

    bad_phrase = verifier.verify(
        CardSpec("survival:thank you:english_to_japanese", "survival", None, "english_to_japanese", "thank you"),
        GeneratedQuestion("?", ["bad", "worse", "worst"], 0, "", {}),
        vocab,
    )
    assert "survival english_to_japanese choices not in whitelist" in bad_phrase.issues
    assert "survival english_to_japanese correct mismatch" in bad_phrase.issues

    bad_phrase_reverse = verifier.verify(
        CardSpec("vocab:friend:japanese_to_english", "vocab", None, "japanese_to_english", "friend"),
        GeneratedQuestion("?", ["bad", "worse", "worst"], 0, "", {}),
        vocab,
    )
    assert "vocab japanese_to_english choices not in whitelist" in bad_phrase_reverse.issues
    assert "vocab japanese_to_english correct mismatch" in bad_phrase_reverse.issues

    unknown_phrase = verifier.verify(
        CardSpec("vocab:friend:bad", "vocab", None, "bad", "friend"),
        GeneratedQuestion("?", ["友達", "駅", "水"], 0, "", {}),
        vocab,
    )
    assert "unknown vocab variant" in unknown_phrase.issues

    missing_keigo = verifier.verify(
        CardSpec("keigo:missing:plain_to_keigo", "keigo", None, "plain_to_keigo", "missing"),
        GeneratedQuestion("?", ["申し上げる", "拝見する", "伺う"], 0, "", {}),
        vocab,
    )
    assert "keigo base missing in whitelist" in missing_keigo.issues

    bad_keigo = verifier.verify(
        CardSpec("keigo:言う:plain_to_keigo", "keigo", None, "plain_to_keigo", "言う"),
        GeneratedQuestion("?", ["bad", "worse", "worst"], 0, "plain English", {}),
        vocab,
    )
    assert "keigo choices not in whitelist" in bad_keigo.issues
    assert "keigo correct answer mismatch" in bad_keigo.issues

    classification = verifier.verify(
        CardSpec("keigo:言う:politeness_classification", "keigo", None, "politeness_classification", "言う"),
        GeneratedQuestion("?", ["One", "Two", "Three"], 0, "", {}),
        vocab,
    )
    assert "keigo classification choices invalid" in classification.issues
    assert "keigo classification correct mismatch" in classification.issues

    unknown_keigo = verifier.verify(
        CardSpec("keigo:言う:bad", "keigo", None, "bad", "言う"),
        GeneratedQuestion("?", ["申し上げる", "拝見する", "伺う"], 0, "", {}),
        vocab,
    )
    assert "unknown keigo variant" in unknown_keigo.issues

    jp_explanation = verifier.verify(
        CardSpec("keigo:言う:plain_to_keigo", "keigo", None, "plain_to_keigo", "言う"),
        GeneratedQuestion("?", ["申し上げる", "拝見する", "伺う"], 0, "説明です", {}),
        vocab,
    )
    assert "explanation includes non-whitelisted Japanese text" in jp_explanation.issues
