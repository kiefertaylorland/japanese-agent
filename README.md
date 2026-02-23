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
