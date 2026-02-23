# japanese-agent

CLI Japanese study agent with SRS (hiragana, katakana, kanji, keigo).

## Why this project

This project shows how I design practical, user-facing automation with clear workflows, clean CLI ergonomics, and iterative quality engineering.

## Quickstart

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

jp-agent init --sync
jp-agent study kana
```

## Commands

- `jp-agent init` — initialize SQLite DB and optionally sync cards
- `jp-agent study MODE` — run study sessions (`kana`, `hiragana`, `katakana`, `kanji`, `keigo`)
- `jp-agent stats` — review progress and accuracy

## New Learning Packs

Added curated datasets for practical study:

- `data/core_vocab_survival.json` — foundational daily-life vocabulary (people, places, food, adjectives)
- `data/survival_phrases.json` — travel/social survival phrases with Japanese, kana, and romaji

These are currently **data packs** (not a built-in `study` mode yet), and can be used directly now via JSON tooling.

### How to use the new vocab/phrases right now

```bash
# List categories in core vocab
jq -r '.[].category' data/core_vocab_survival.json | sort -u

# Preview vocab words (English -> Japanese / kana / romaji)
jq -r '.[] | "\(.english) -> \(.japanese) / \(.kana) / \(.romaji)"' data/core_vocab_survival.json | head -n 25

# Search for a word/phrase
jq -r '.[] | select(.english|test("wallet|airport|expensive"; "i"))' data/core_vocab_survival.json
jq -r '.[] | select(.english|test("thank you|where is the ATM|table for two"; "i"))' data/survival_phrases.json

# Print all survival phrases
jq -r '.[] | "\(.english) -> \(.japanese) / \(.kana) / \(.romaji)"' data/survival_phrases.json
```

### Current `jp-agent` study modes

```bash
jp-agent study kana
jp-agent study hiragana
jp-agent study katakana
jp-agent study kanji --level N5
jp-agent study keigo --context meeting
```

> Note: `core_vocab_survival.json` and `survival_phrases.json` are committed and ready; CLI modes like `jp-agent study vocab` / `jp-agent study survival` can be added next.

## Work With Me

- 📅 15-min automation audit: https://calendly.com/kiefertaylorland/15-minute-meeting
- ✉️ Email: kiefertaylorland@gmail.com
- 💼 LinkedIn: https://www.linkedin.com/in/kieferland/
- 🌐 Portfolio: https://kiefertaylorland.github.io/portfolio/

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q
```
