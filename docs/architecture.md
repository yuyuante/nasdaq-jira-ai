# Architecture

The project uses a small, dependency-inverted layout:

```text
src/nasdaq_jira/
├── config.py          YAML loading and typed application settings
├── logging_config.py  application logging setup
├── crawler.py         Playwright navigation and retry coordination
├── parser.py          Jira DOM row to domain model conversion
├── models.py          immutable domain models
├── repository.py      persistence contracts (Repository Pattern)
├── storage.py         SQLite repository implementation
├── retry.py           async retry utility
└── cli.py             command-line composition and application flow
```

`__main__.py` only delegates to `cli.main`; it contains no business logic.
The crawler depends on the parser abstraction for DOM conversion, while the CLI
composes the crawler with `SQLiteIssueRepository`. The repository contract keeps
storage replaceable without changing crawler or application logic.

Top-level directories:

- `config/`: YAML configuration templates.
- `scripts/`: thin operational entry points.
- `docs/`: design and maintenance documentation.
- `tests/`: unit and integration-test code.