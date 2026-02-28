# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**jp-agent** is a CLI-based Japanese learning application using Spaced Repetition System (SRS). It allows users to study hiragana, katakana, kanji, honorific language (keigo), core vocabulary, and survival phrases.

## Setup & Common Commands

### Installation
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

### Database & Sync
```bash
# Initialize database and optionally sync cards from vocab files
jp-agent init                  # Initialize DB schema
jp-agent init --sync           # Initialize and build cards from vocab data
```

### Running Study Sessions
```bash
jp-agent study kana            # Mixed hiragana/katakana
jp-agent study hiragana
jp-agent study katakana
jp-agent study kanji --level N5  # Levels: N5, N4, N3, N2
jp-agent study keigo --context email  # Context: email, meeting
jp-agent study vocab           # Core vocabulary
jp-agent study survival        # Survival/travel phrases
jp-agent study [mode] --count 50  # Override default count (30)
```

### Stats & Monitoring
```bash
jp-agent stats                 # View total cards, due cards, accuracy metrics
```

### Testing
```bash
pytest                         # Run all tests
pytest -v                      # Verbose output
pytest tests/test_srs.py       # Run single test file
pytest tests/test_srs.py::test_srs_correct_increases_interval_and_ease  # Single test
```

## Architecture

### Core Layers

**1. CLI Layer (`cli.py`)**
- Entry point using Typer framework
- Three main commands: `init`, `study`, `stats`
- Validates mode and level arguments
- Coordinates vocab loading, DB access, and quiz execution

**2. Database Layer (`db.py`)**
- SQLite operations for cards, reviews, and vocab file hashes
- Three main tables:
  - `cards`: Study cards with SRS state (ease, interval, due_date)
  - `reviews`: Historical review records with timestamps and performance metrics
  - `vocab_files`: SHA256 hashes to detect vocab file changes
- Key operations: fetch due/next cards, sync cards, update reviews, generate stats
- All card IDs include mode and variant info for lookup

**3. Vocab System (`vocab.py`)**
- Loads JSON vocab files from `data/` directory
- Five vocab types: hiragana, katakana, kanji (per level), keigo, core_vocab, survival_phrases
- `VocabStore` dataclass normalizes all vocab across different JSON structures
- Validates keigo entries against `VALID_KEIGO_TYPES` (sonkeigo, kenjogo, teineigo)
- SHA256-based change detection prevents stale card data

**4. Card System (`cards.py`)**
- Builds `CardSpec` objects from vocab entries
- Each card has a deterministic `card_id` = `mode:variant:key` for SRS state matching
- Separates variant representation (hiragana vs katakana for kana modes) from study content
- Different modes use different variant strategies

**5. Agent System** (directory: `agents/`)
- **PlannerAgent** (`planner.py`): Selects which cards to study
  - Prioritizes due cards (overdue)
  - Fills remaining slots from upcoming cards (randomized)
  - Special handling for "kana" mode: mixes hiragana and katakana
- **SrsAgent** (`srs.py`): Updates card state after reviews
  - SM-2 algorithm variant: adjusts ease (1.3–2.5) and interval based on correctness
  - Correct: interval multiplied by ease, ease +0.1, randomized
  - Incorrect: interval resets to 1, ease -0.2 (minimum 1.3)
- **GeneratorAgent** (`generator.py`): Creates multiple-choice questions
  - Uses OpenAI API for keigo questions (contextual classification)
  - Template-based for kana, kanji, vocab, survival modes
- **VerifierAgent** (`verifier.py`): Validates generated questions
  - Checks correctness, uniqueness, and prompt clarity

**6. Quiz Layer (`quiz.py`)**
- Orchestrates study session workflow
- Loads plan → generates questions → displays prompts → collects responses → updates SRS
- Tracks response time for statistics

### Data Flow

1. **Init** → vocab files → `VocabStore` → `CardSpec` list → SQLite cards table
2. **Study** → `StudyRequest` → `PlannerAgent.plan()` → selected cards → `GeneratorAgent` → quiz loop → `SrsAgent.apply()` → SQLite reviews table

### Study Modes

- **Hiragana/Katakana**: Recognize character → romaji (template-based)
- **Kanji**: Recognize kanji → English meanings (template-based, N5/N4/N3/N2 levels)
- **Keigo**: Classify polite forms (sonkeigo, kenjogo, teineigo) → LLM-generated context awareness
- **Vocab/Survival**: Recognize Japanese/kana → English definitions (template-based)

## Key Files & Responsibilities

| File | Purpose |
|------|---------|
| `cli.py` | Command routing, arg validation, path management |
| `db.py` | SQLite schema, CRUD operations, query builders |
| `vocab.py` | JSON loading, vocab validation, data structures |
| `cards.py` | Card ID generation, variant management |
| `quiz.py` | Study session orchestration |
| `agents/planner.py` | Card selection strategy |
| `agents/srs.py` | Spaced repetition algorithm |
| `agents/generator.py` | Question generation (LLM or template) |
| `agents/verifier.py` | Question validation |
| `models.py` | Frozen dataclasses for immutable domain objects |
| `config.py` | Path resolution, environment defaults |
| `llm.py` | OpenAI API configuration |

## Important Design Patterns

1. **Immutable Data**: All model classes are frozen dataclasses to ensure domain purity
2. **Card ID Determinism**: `card_id = mode:variant:key` allows matching with vocab for question generation
3. **Vocab Hash Tracking**: SHA256 hashes in DB detect when vocab files change; triggers sync needed
4. **SRS State Isolation**: Card ease and interval stored separately from volatile review metadata
5. **Agent Composition**: Each agent handles one responsibility (planning, generation, verification, scheduling)

## Testing Strategy

Tests use pytest with a `vocab_dir` fixture (conftest.py) providing temporary JSON vocab files. This avoids external dependencies while testing the full vocab → card → quiz flow.

Current test coverage:
- `test_planner.py`: Card selection and prioritization
- `test_srs.py`: Ease/interval calculations
- `test_generator_verifier.py`: Question generation and validation
- `test_vocab.py`: Vocab loading and validation
- `test_survival_modes.py`: Vocab and survival phrase integration
- `test_hashes.py`: Hash mismatch detection

## Debugging Tips

- **Vocab Sync Issues**: Run `jp-agent init --sync` if hash validation fails
- **DB Issues**: Check `jp_agent.db` or use `--db` flag for alternate path
- **LLM Failures**: Ensure `OPENAI_API_KEY` is set; keigo mode requires it
- **Test Failures**: Check fixture setup in `conftest.py` for vocab structure assumptions
