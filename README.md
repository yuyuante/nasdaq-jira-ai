# Nasdaq Jira Crawler

Production-oriented Python 3.13 crawler for Jira search pages, backed by SQLite.
The crawler uses Playwright and a persisted browser session so it can work with
private Jira installations without putting credentials in configuration files.

## Quick start

```bash
python -m venv .venv
# macOS/Linux
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/playwright install chromium
# Windows PowerShell
.venv\Scripts\python -m pip install -e ".[dev]"
.venv\Scripts\playwright install chromium
```

Copy `.env.example` to `.env` for local environment overrides. Keep credentials
out of Git. Configure selectors and the Jira search URL in
`config/config.example.yaml` (or a local `config/config.yaml`).

The `--login` command opens a headed browser; complete Jira login and press
Enter in the terminal to save `storage_state.json`.

```bash
nasdaq-jira --config config/config.example.yaml --login
nasdaq-jira --config config/config.example.yaml
```

## Docker

```bash
docker compose run --rm crawler
```

Mount `storage_state.json`, `data/`, and `logs/` as volumes. The default
container command uses the example configuration; copy it to
`config/config.yaml` for real use.

## Development setup

The project targets Python 3.13. Install the development dependencies and
Playwright browser, then install the Git hooks:

```bash
python -m pip install -e ".[dev]"
python -m playwright install chromium
pre-commit install
```

Run the complete local validation suite:

```bash
pre-commit run --all-files
ruff check .
ruff format --check .
black --check .
mypy src
pytest
```

The pre-commit hooks run Ruff check, Ruff format, Black, and MyPy. Tests do not
contact Jira; crawler integration tests should use a controlled test server.

Do not commit real credentials, cookies, or a populated browser state file.
