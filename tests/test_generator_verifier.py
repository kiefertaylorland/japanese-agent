from __future__ import annotations

import random

from jp_agent.agents.generator import ContentGeneratorAgent
from jp_agent.agents.verifier import VerifierAgent
from jp_agent.models import CardSpec, StudyRequest
from jp_agent.vocab import load_vocab_for_mode


def test_kana_generator_and_verifier(vocab_dir):
    vocab = load_vocab_for_mode(vocab_dir, "hiragana", None)
    generator = ContentGeneratorAgent(vocab)
    verifier = VerifierAgent()
    card = CardSpec(
        card_id="hiragana:a:kana_to_romaji",
        mode="hiragana",
        level=None,
        variant="kana_to_romaji",
        vocab_key="a",
    )
    request = StudyRequest(mode="hiragana", level=None, context=None, count=1, seed=123)
    question = generator.generate(card, request, random.Random(1))
    verified = verifier.verify(card, question, vocab)
    assert verified.valid
    assert len(question.choices) == 3


def test_keigo_classification_generator_and_verifier(vocab_dir):
    vocab = load_vocab_for_mode(vocab_dir, "keigo", None)
    generator = ContentGeneratorAgent(vocab)
    verifier = VerifierAgent()
    card = CardSpec(
        card_id="keigo:言う:politeness_classification",
        mode="keigo",
        level=None,
        variant="politeness_classification",
        vocab_key="言う",
    )
    request = StudyRequest(mode="keigo", level=None, context=None, count=1, seed=123)
    question = generator.generate(card, request, random.Random(1))
    verified = verifier.verify(card, question, vocab)
    assert verified.valid
    assert set(question.choices) == {"Sonkeigo", "Kenjogo", "Teineigo"}
