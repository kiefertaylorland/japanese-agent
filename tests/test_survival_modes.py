from __future__ import annotations

from jp_agent.agents.generator import ContentGeneratorAgent
from jp_agent.agents.verifier import VerifierAgent
from jp_agent.cards import build_all_cards
from jp_agent.models import StudyRequest
from jp_agent.vocab import load_all_vocab, load_vocab_for_mode


def test_load_vocab_mode(vocab_dir):
    vocab = load_vocab_for_mode(vocab_dir, "vocab", None)
    assert len(vocab.core_vocab) == 3
    assert vocab.core_vocab[0].english


def test_load_survival_mode(vocab_dir):
    vocab = load_vocab_for_mode(vocab_dir, "survival", None)
    assert len(vocab.survival_phrases) == 3
    assert vocab.survival_phrases[0].japanese


def test_generator_and_verifier_for_new_modes(vocab_dir):
    vocab = load_all_vocab(vocab_dir)
    cards = build_all_cards(vocab)

    vocab_card = next(c for c in cards if c.mode == "vocab")
    survival_card = next(c for c in cards if c.mode == "survival")

    generator = ContentGeneratorAgent(vocab=vocab, llm=None)
    verifier = VerifierAgent()

    req = StudyRequest(mode="vocab", level=None, context=None, count=5, seed=42)
    import random
    rng = random.Random(42)

    q1 = generator.generate(vocab_card, req, rng)
    v1 = verifier.verify(vocab_card, q1, vocab)
    assert v1.valid

    req2 = StudyRequest(mode="survival", level=None, context=None, count=5, seed=7)
    rng2 = random.Random(7)
    q2 = generator.generate(survival_card, req2, rng2)
    v2 = verifier.verify(survival_card, q2, vocab)
    assert v2.valid
