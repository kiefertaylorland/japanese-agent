from __future__ import annotations

import re
from typing import Iterable

_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f-\x9f]")


def sanitize_text(text: str) -> str:
    return _CONTROL_RE.sub("", text)


def sanitize_lines(lines: Iterable[str]) -> list[str]:
    return [sanitize_text(line) for line in lines]
