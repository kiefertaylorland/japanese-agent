from __future__ import annotations

import random
from datetime import date
from typing import Iterable

from jp_agent import db
from jp_agent.cards import parse_vocab_key
from jp_agent.models import CardSpec, Plan, StudyRequest


class PlannerAgent:
    def plan(self, conn, request: StudyRequest) -> Plan:
        today_iso = date.today().isoformat()
        if request.mode == "kana":
            rows = self._fetch_mixed_kana(conn, today_iso, request.count)
        else:
            due_rows = db.fetch_due_cards(
                conn, request.mode, request.level, today_iso, request.count, randomize=True
            )
            remaining = request.count - len(due_rows)
            if remaining > 0:
                next_rows = db.fetch_next_cards(
                    conn, request.mode, request.level, today_iso, remaining, randomize=True
                )
                rows = list(due_rows) + list(next_rows)
            else:
                rows = list(due_rows)

        card_specs = [self._row_to_card(row) for row in rows]
        rng = random.Random(request.seed)
        rng.shuffle(card_specs)
        return Plan(card_specs=card_specs)

    def _fetch_mixed_kana(self, conn, today_iso: str, count: int):
        due_hira = db.fetch_due_cards(conn, "hiragana", None, today_iso, count, randomize=True)
        due_kata = db.fetch_due_cards(conn, "katakana", None, today_iso, count, randomize=True)
        due_rows = list(due_hira) + list(due_kata)
        rng = random.Random()
        rng.shuffle(due_rows)
        if len(due_rows) >= count:
            return due_rows[:count]

        remaining = count - len(due_rows)
        next_hira = db.fetch_next_cards(conn, "hiragana", None, today_iso, remaining, randomize=True)
        next_kata = db.fetch_next_cards(conn, "katakana", None, today_iso, remaining, randomize=True)
        next_rows = list(next_hira) + list(next_kata)
        rng.shuffle(next_rows)
        return due_rows + next_rows[:remaining]

    def _row_to_card(self, row) -> CardSpec:
        card_id = str(row["card_id"])
        mode = str(row["mode"])
        level = row["level"]
        variant = str(row["variant"])
        vocab_key = parse_vocab_key(card_id, mode)
        return CardSpec(card_id=card_id, mode=mode, level=level, variant=variant, vocab_key=vocab_key)
