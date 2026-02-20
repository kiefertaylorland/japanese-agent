# jp-agent

CLI Japanese study agent with SRS (hiragana, katakana, kanji, keigo).

## Quickstart

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

jp-agent init --sync
jp-agent study kana
```

Notes:

- Vocab files are read from `./data/` (see `docs/vocab_schema.md`).
- Architecture overview: `docs/ARCHITECTURE.md`.
- Progress is stored in `jp_agent.db` by default (override with `--db` or `JP_AGENT_DB`).

## Install

Runtime only:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Commands

### init

Initialize the database and optionally sync cards from vocab files.

```bash
jp-agent init [OPTIONS]
```

**Options:**

- `--sync` - Build or update cards from vocab files
- `--db PATH` - Path to SQLite DB (default: `jp_agent.db` in the current directory or `JP_AGENT_DB`)

**Example:**

```bash
jp-agent init --sync
```

### study

Run a study quiz for a specific mode and optional level.

```bash
jp-agent study MODE [OPTIONS]
```

**Modes:**

- `kana` - Mixed hiragana + katakana
- `hiragana` - Study hiragana characters
- `katakana` - Study katakana characters
- `kanji` - Study kanji (requires `--level`)
- `keigo` - Study keigo (polite language)

**Options:**

- `--level {N5,N4,N3,N2}` - Kanji level (required for kanji mode)
- `--context TEXT` - Keigo context (e.g., email, meeting)
- `--count N` - Number of questions (default: 30)
- `--db PATH` - Path to SQLite DB

**Examples:**

```bash
jp-agent study kana
jp-agent study hiragana
jp-agent study katakana --count 20
jp-agent study kanji --level N5
jp-agent study kanji --level N3 --count 15
jp-agent study keigo --context email
```

### stats

Display study statistics including total cards, due cards, and accuracy metrics.

```bash
jp-agent stats [OPTIONS]
```

**Options:**

- `--db PATH` - Path to SQLite DB

**Output includes:**

- Total cards
- Due cards (cards ready to review)
- 7-day accuracy
- 30-day accuracy
- Breakdown by mode

**Example:**

```bash
jp-agent stats
```

## Wrapper Script

If you prefer not to activate your virtualenv, you can use the wrapper script (it uses `.venv` if present):

```bash
./bin/jp-agent init --sync
./bin/jp-agent study kanji --level N5
```

## Optional LLM explanations for keigo

For keigo mode, you can enable LLM explanations by setting these environment variables:

```bash
export OPENAI_API_KEY=...
export OPENAI_MODEL=...
```

## Troubleshooting

- If you see `TyperArgument.make_metavar() takes 1 positional argument but 2 were given`, you likely have an incompatible Click version installed. This project pins Click to `8.1.7`. Reinstall in a fresh venv.

## Dev setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q
```
