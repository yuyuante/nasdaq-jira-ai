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

Copy `.env.example` to `.env` for local environment overrides. YAML is validated with Pydantic; `NASDAQ_JIRA_` environment variables use `__` for nested fields and take precedence over `.env` and YAML. Keep credentials
out of Git. Configure selectors and the Jira search URL in
`config/config.example.yaml` (or a local `config/config.yaml`). Required values are validated by Pydantic before the crawler starts.

The `--login` command opens a headed browser; complete Jira login and press
Enter in the terminal to save `storage_state.json`.

```bash
nasdaq-jira --config config/config.example.yaml --login
nasdaq-jira --config config/config.example.yaml
```

Login is completed manually in the headed browser, so MFA is supported without storing credentials in the project. A successful login saves `storage_state.json`; normal crawls reuse it automatically. If the session expires or cannot be verified, the CLI stops with a message instructing you to run `--login` again. Configure `browser.authenticated_selector` and `browser.login_selector` for the target Jira deployment.

## Project layout

```text
src/       application package and domain modules
tests/     automated tests
config/    YAML configuration templates
scripts/   thin operational entry points
docs/      architecture and maintenance documentation

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

### Make targets

The Makefile provides consistent development commands. Set `PYTHON` to select
a Python executable, for example `make PYTHON=python3.13 check`.

| Target | Description |
| --- | --- |
| `make install` | Install the project, development dependencies, and Chromium for Playwright. |
| `make lint` | Run Ruff lint checks. |
| `make format` | Format Python files with Ruff format and Black. |
| `make typecheck` | Run MyPy against the application source. |
| `make test` | Run the pytest test suite. |
| `make check` | Run lint, formatting checks, type checking, and tests without modifying files. |
| `make clean` | Remove Python caches, test artifacts, and build outputs. |