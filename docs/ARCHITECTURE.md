# Architecture

`jp-agent` is a terminal study app that uses a small set of cooperating agents to keep content correct and progress persistent.

## High-Level Flow

1. **Planner Agent** selects which cards to review next (based on SRS scheduling).
2. **Content Generator Agent** builds a multiple-choice question from whitelisted vocab only.
3. **Verifier Agent** validates that the question/answers match the whitelist and are unambiguous.
4. **SRS/Logger Agent** updates the card’s interval/ease and logs the review outcome in SQLite.

## Data Sources

- Static vocab JSON files in `data/` (see `docs/vocab_schema.md`)
- Local SQLite DB (default: `jp_agent.db`)

Vocab file hashes are stored in the DB. If a vocab file changes, `study` will refuse to run until you re-sync with `jp-agent init --sync`.

## Agents

### Planner Agent (`jp_agent/agents/planner.py`)

- Input: `StudyRequest(mode, level, context, count, seed)` + SQLite `cards` table
- Output: `Plan(card_specs=[...])`
- Policy: due-first selection with randomized sampling

### Content Generator Agent (`jp_agent/agents/generator.py`)

- Input: `CardSpec` + whitelisted vocab in memory
- Output: `GeneratedQuestion(prompt, choices, correct_index, explanation, meta)`
- Constraints:
  - **No dynamic vocab generation**. All choices must come from whitelisted vocab lists.
  - Keigo explanations can optionally use an LLM, but the verifier will reject explanations that contain non-whitelisted Japanese text.

### Verifier Agent (`jp_agent/agents/verifier.py`)

- Validates:
  - Correct answer index in range
  - No duplicate choices
  - All choices are in the whitelist for the card’s mode/level
  - Keigo classification questions match the entry’s `type`

### SRS/Logger Agent (`jp_agent/agents/srs.py`)

Implements a simplified SM-2 style update:

- If correct:
  - `interval = round(interval * ease)` (min 1)
  - `ease += 0.1` (max 2.5)
- If incorrect:
  - `interval = 1`
  - `ease -= 0.2` (min 1.3)

Writes both the updated card state and an append-only row in `reviews`.

## SQLite Schema

Tables:

- `cards`: one row per card variant (`card_id`), stores ease/interval/due date
- `reviews`: append-only review log (correctness + response time + before/after)
- `vocab_files`: filename -> sha256 hash and updated_at

Schema is created by `jp_agent/db.py::ensure_schema()`.
