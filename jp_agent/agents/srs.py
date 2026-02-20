from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from jp_agent import db


@dataclass(frozen=True)
class SrsResult:
    ease_after: float
    interval_after: int
    due_date: date


def update_srs(ease: float, interval: int, correct: bool) -> SrsResult:
    if correct:
        new_interval = max(1, round(interval * ease))
        new_ease = min(2.5, ease + 0.1)
    else:
        new_interval = 1
        new_ease = max(1.3, ease - 0.2)
    due_date = date.today() + timedelta(days=new_interval)
    return SrsResult(ease_after=new_ease, interval_after=new_interval, due_date=due_date)


class SrsAgent:
    def apply(self, conn, card_row, correct: bool, response_ms: int) -> SrsResult:
        ease_before = float(card_row["ease"])
        interval_before = int(card_row["interval"])
        result = update_srs(ease_before, interval_before, correct)
        db.update_review(
            conn,
            card_id=str(card_row["card_id"]),
            correct=correct,
            response_ms=response_ms,
            ease_before=ease_before,
            ease_after=result.ease_after,
            interval_before=interval_before,
            interval_after=result.interval_after,
            due_date_iso=result.due_date.isoformat(),
        )
        return result
