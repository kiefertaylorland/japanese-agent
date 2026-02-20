from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class StudyRequest:
    mode: str
    level: str | None
    context: str | None
    count: int
    seed: int


@dataclass(frozen=True)
class CardSpec:
    card_id: str
    mode: str
    level: str | None
    variant: str
    vocab_key: str


@dataclass(frozen=True)
class Plan:
    card_specs: list[CardSpec]


@dataclass(frozen=True)
class GeneratedQuestion:
    prompt: str
    choices: list[str]
    correct_index: int
    explanation: str
    meta: dict[str, Any]


@dataclass(frozen=True)
class VerifiedQuestion:
    valid: bool
    question: GeneratedQuestion
    issues: list[str]
