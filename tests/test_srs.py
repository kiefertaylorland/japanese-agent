from __future__ import annotations

from jp_agent.agents.srs import update_srs


def test_srs_correct_increases_interval_and_ease():
    result = update_srs(ease=2.0, interval=3, correct=True)
    assert result.interval_after >= 1
    assert result.ease_after > 2.0


def test_srs_incorrect_resets_interval_and_decreases_ease():
    result = update_srs(ease=2.0, interval=3, correct=False)
    assert result.interval_after == 1
    assert result.ease_after < 2.0
