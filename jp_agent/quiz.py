from __future__ import annotations

import random
import time
from datetime import date

from jp_agent import db
from jp_agent.agents.generator import ContentGeneratorAgent
from jp_agent.agents.planner import PlannerAgent
from jp_agent.agents.srs import SrsAgent
from jp_agent.agents.verifier import VerifierAgent
from jp_agent.llm import LlmConfig
from jp_agent.models import StudyRequest
from jp_agent.utils import sanitize_text
from jp_agent.vocab import VocabStore


def run_quiz(conn, request: StudyRequest, vocab: VocabStore, llm: LlmConfig | None) -> None:
    planner = PlannerAgent()
    generator = ContentGeneratorAgent(vocab=vocab, llm=llm)
    verifier = VerifierAgent()
    srs_agent = SrsAgent()

    plan = planner.plan(conn, request)
    if not plan.card_specs:
        print("No cards available for review.")
        return

    rng = random.Random(request.seed)

    for idx, card in enumerate(plan.card_specs, start=1):
        card_row = db.fetch_card(conn, card.card_id)
        if card_row is None:
            print(f"Skipping missing card: {card.card_id}")
            continue

        question = None
        use_llm = True
        issues: list[str] = []
        for _ in range(3):
            try:
                generated = generator.generate(card, request, rng, use_llm=use_llm)
            except Exception as exc:
                issues = [str(exc)]
                break
            verified = verifier.verify(card, generated, vocab)
            if verified.valid:
                question = verified.question
                break
            issues = verified.issues
            if "explanation includes non-whitelisted Japanese text" in issues:
                use_llm = False
        if question is None:
            print(f"Skipping card due to invalid question: {card.card_id}")
            if issues:
                print(f"Issues: {', '.join(issues)}")
            continue

        prompt = sanitize_text(question.prompt)
        print(f"Q{idx}: {prompt}")
        for choice_idx, choice in enumerate(question.choices, start=1):
            print(f"{choice_idx}) {sanitize_text(choice)}")

        start = time.monotonic()
        answer_index = _prompt_for_answer(len(question.choices))
        elapsed_ms = int((time.monotonic() - start) * 1000)

        correct = answer_index == question.correct_index
        if correct:
            print("✔ Correct")
        else:
            correct_choice = sanitize_text(question.choices[question.correct_index])
            print(f"✘ Incorrect. Correct answer: {correct_choice}")

        result = srs_agent.apply(conn, card_row, correct, elapsed_ms)

        if question.explanation:
            print("")
            print(sanitize_text(question.explanation))

        if card.mode == "keigo":
            usage = sanitize_text(question.meta.get("usage", ""))
            polite = sanitize_text(question.meta.get("type", ""))
            if usage:
                print(f"Usage: {usage}")
            if polite:
                print(f"Politeness level: {polite}")

        print(f"Next review: {result.interval_after} days")
        print("")


def _prompt_for_answer(choice_count: int) -> int:
    while True:
        raw = input("Your answer: ").strip()
        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < choice_count:
                return idx
        print(f"Please enter a number between 1 and {choice_count}.")
