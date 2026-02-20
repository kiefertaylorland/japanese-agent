from __future__ import annotations

import json

import pytest

from jp_agent.vocab import load_keigo


def test_keigo_validation_rejects_invalid_type(tmp_path):
    data = [
        {
            "base": "言う",
            "keigo": "申し上げる",
            "type": "invalid",
            "meaning": "to say",
            "usage": "business",
            "example_contexts": ["email"],
        }
    ]
    path = tmp_path / "keigo_basic.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError):
        load_keigo(path)
