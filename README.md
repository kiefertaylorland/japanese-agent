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
## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q
```

## Commands

- `jp-agent init` — initialize SQLite DB and optionally sync cards
- `jp-agent study MODE` — run study sessions (`kana`, `hiragana`, `katakana`, `kanji`, `keigo`, `vocab`, `survival`)
- `jp-agent stats` — review progress and accuracy

## New Learning Packs

Added curated datasets for practical study:

- `data/core_vocab_survival.json` — foundational daily-life vocabulary (people, places, food, adjectives)
- `data/survival_phrases.json` — travel/social survival phrases with Japanese, kana, and romaji

These are integrated into the CLI study flow and can be practiced like other modes.

### Current `jp-agent` study modes

```bash
jp-agent study kana
jp-agent study hiragana
jp-agent study katakana
jp-agent study kanji --level N5
jp-agent study keigo --context meeting
jp-agent study vocab
jp-agent study survival
```

## Work With Me

- 📅 15-min discovery call: https://calendly.com/kiefertaylorland/15-minute-meeting
- ✉️ Email: kiefertaylorland@gmail.com
- 💼 LinkedIn: https://www.linkedin.com/in/kieferland/
- 🌐 Portfolio: https://kiefertaylorland.github.io/portfolio/
