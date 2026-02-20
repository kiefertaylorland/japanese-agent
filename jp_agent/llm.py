from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class LlmConfig:
    client: object
    model: str


def get_llm_config() -> LlmConfig | None:
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL")
    if not api_key or not model:
        return None
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    return LlmConfig(client=client, model=model)
