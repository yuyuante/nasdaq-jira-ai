# Nasdaq Jira Crawler

Production-oriented Python 3.12 crawler for Jira search pages, backed by SQLite.
The crawler uses Playwright and a persisted browser session so it can work with
private Jira installations without putting credentials in configuration files.

## Quick start

```bash
python -m venv .venv
.venv/bin/pip install -e '.[dev]'
playwright install chromium
nasdaq-jira --config config/config.example.yaml --login
nasdaq-jira --config config/config.example.yaml
```

On Windows, use `.venv\Scripts\pip` and `.venv\Scripts\nasdaq-jira`.
The `--login` command opens a headed browser; complete Jira login and close the
browser to save `storage_state.json`.

Configuration is YAML. See `config/config.example.yaml` for selectors and the
search URL. Selectors are deliberately configurable because Jira themes and
versions differ.

## Docker

```bash
docker compose run --rm crawler
```

Mount `storage_state.json` and `data/` as volumes. The default container command
uses the example configuration; copy it to `config/config.yaml` for real use.

## Development

```bash
ruff check .
black --check .
mypy src
pytest
```

Do not commit real credentials, cookies, or a populated browser state file.

