# Nasdaq Jira Crawler

Nasdaq Jira 爬蟲與 AI 知識庫。支援 Python 3.13、Playwright、Jira REST API、SQLite、增量同步與 RAG 問答。

A production-oriented Nasdaq Jira crawler and AI knowledge base. It supports Python 3.13, Playwright, the Jira REST API, SQLite, incremental synchronization, and RAG-based question answering.

## 快速開始 / Quick start

```bash
python -m venv .venv
# macOS/Linux
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/playwright install chromium
# Windows PowerShell
.venv\Scripts\python -m pip install -e ".[dev]"
.venv\Scripts\playwright install chromium
```

複製 `.env.example` 為 `.env` 以設定本機環境變數。YAML 會以 Pydantic 驗證；`NASDAQ_JIRA_` 環境變數使用 `__` 表示巢狀欄位，優先於 `.env` 與 YAML。請勿將憑證提交至 Git。

Copy `.env.example` to `.env` for local overrides. YAML is validated with Pydantic. `NASDAQ_JIRA_` environment variables use `__` for nested fields and take precedence over `.env` and YAML. Never commit credentials.

請在 `config/config.example.yaml` 或本機 `config/config.yaml` 設定 Jira URL 與 selectors。

Configure the Jira URL and selectors in `config/config.example.yaml` or a local `config/config.yaml`.

## 登入與爬取 / Login and crawling

`--login` 會開啟可見的 Chromium。請在瀏覽器完成 Jira 登入與 MFA，再回到終端機按 Enter；登入狀態會儲存為 `storage_state.json`，後續執行會自動重用。

The `--login` command opens a visible Chromium browser. Complete Jira login and MFA, then press Enter in the terminal. The session is saved to `storage_state.json` and reused automatically.

```powershell
python -m nasdaq_jira --config config/config.yaml --login
python -m nasdaq_jira --config config/config.yaml
```

Windows 批次檔也已提供常用指令包裝：

```bat
scripts\nasdaq-jira.bat login
scripts\nasdaq-jira.bat crawl
scripts\nasdaq-jira.bat sync
scripts\nasdaq-jira.bat sync-full
scripts\nasdaq-jira.bat sync-resume
scripts\nasdaq-jira.bat ask "Why did FIX Session disconnect?"
scripts\nasdaq-jira.bat show XTAIFEX-306
scripts\nasdaq-jira.bat show XTAIFEX-306 --all-comments
```

The Windows batch wrapper provides the same common commands. It uses `.venv` when available, otherwise it falls back to `python`. Create `config/config.yaml` locally before running it.
若 session 過期，請重新執行 `--login`。請勿提交 cookies 或已填入內容的 `storage_state.json`。

If the session expires, run `--login` again. Do not commit cookies or a populated `storage_state.json`.

顯示本機 Ticket / Show a stored ticket

`show` 預設只讀取 SQLite 並顯示 Comments 統一摘要；加上 `--all-comments` 可列出所有 Comments。兩者都不需要 Jira 連線或 OpenAI API Key：

The `show` command reads SQLite only. It does not require a Jira connection or OpenAI API key. By default, it displays issue details, description, comment summaries, attachments, and history; add `--all-comments` to display every raw comment:

```bat
scripts\nasdaq-jira.bat show XTAIFEX-306
scripts\nasdaq-jira.bat show XTAIFEX-306 --all-comments
```

## 專案結構 / Project layout

```text
src/nasdaq_jira/       application and domain modules / 應用程式與領域模組
tests/                 automated tests / 自動化測試
config/                YAML templates / YAML 設定範本
scripts/               operational scripts / 作業腳本
docs/                  architecture documentation / 架構文件
```

## 資料來源 / Data sources

應用程式只依賴 `JiraDataSource` 介面。`JiraApiDataSource` 使用 Jira REST API v2；`JiraPlaywrightDataSource` 重用既有 Chromium session 與 parser。業務邏輯不需要知道實際傳輸方式。

The application depends only on the `JiraDataSource` interface. `JiraApiDataSource` uses Jira REST API v2, while `JiraPlaywrightDataSource` reuses the authenticated Chromium session and parser. Business logic is transport-independent.

```text
CLI / repository
       |
 JiraDataSource
   /          \
REST API   Playwright
```

```yaml
datasource:
  mode: auto  # auto / api / playwright
  api:
    base_url: https://customer-support.nasdaq.com/jira
    token: null
    timeout_ms: 30000
    page_size: 50
```

`auto` 會呼叫 `/rest/api/2/myself`。API 驗證失敗、404、網路錯誤或 API 不可用時會記錄原因並 fallback 至 Playwright。

In `auto` mode, the application calls `/rest/api/2/myself`. Authentication, 404, network, or availability failures are logged and fall back to Playwright.

## Issue 詳細資料與 Comments 摘要 / Issue details and comment summaries

每個 Jira issue 會從詳細頁擷取 Details 欄位、Description、Comments 與 History。原始 issue 會保留在 `jira_issues.issue_json`；Comments 與 History 也會分別寫入 `jira_comments` 與 `jira_history`，方便查詢與增量更新。

Each Jira issue is enriched from its detail page with Details fields, Description, Comments, and History. The original issue snapshot is stored in `jira_issues.issue_json`; comments and history are also normalized into `jira_comments` and `jira_history` for querying and incremental updates.

留言摘要預設採用不需外部服務的抽取式方法，因此爬取資料不需要 AI API Key。原始留言內容會完整保留；儲存的 `body_hash` 可讓未來的 LLM 摘要器只重新處理內容有變更的留言。

By default, comment summaries use a deterministic extractive method, so crawling does not require an AI API key. The original comment body is always preserved, and the stored `body_hash` allows a future LLM summarizer to process only changed comments.
## 增量同步 / Incremental synchronization

同步狀態會儲存在 SQLite 的 `sync_state` 與 `sync_events`。預設使用六小時 overlap window，避免邊界更新遺漏。

Synchronization state is stored in the SQLite `sync_state` and `sync_events` tables. The default six-hour overlap window prevents missed updates at the synchronization boundary.

```yaml
sync:
  mode: incremental
  overlap_hours: 6
  batch_size: 50
  datasource: default
```

```powershell
python -m nasdaq_jira --config config/config.yaml sync
python -m nasdaq_jira --config config/config.yaml sync --full
python -m nasdaq_jira --config config/config.yaml sync --resume
```

增量模式會使用 `updated >= last_sync_time - overlap_hours` JQL。每個成功 batch 都會建立 checkpoint；中斷後使用 `--resume` 從 checkpoint 繼續。事件具備 immutable 與 idempotent 特性。

Incremental mode uses `updated >= last_sync_time - overlap_hours`. Every successful batch creates a checkpoint; `--resume` continues after an interruption. Events are immutable and idempotent.

## AI 知識庫（RAG） / AI knowledge base (RAG)

RAG 會將 Jira summary、description、comments 與 attachments metadata 分 chunk，寫入 SQLite FTS5。Embedding 會依 chunk identity cache，未變更 Issue 不會重複呼叫 embedding provider。

The RAG engine chunks Jira summaries, descriptions, comments, and attachment metadata into SQLite FTS5. Embeddings are cached by chunk identity, so unchanged issues do not call the provider again.

Provider 與 vector store 都是抽象介面；目前提供 OpenAI embedding provider 與 SQLite FTS5 backend，未來可擴充 FAISS、ChromaDB 或 pgvector。

Both the provider and vector store are abstract interfaces. OpenAI embeddings and SQLite FTS5 are the initial implementations; FAISS, ChromaDB, or pgvector can be added later.

```powershell
$env:NASDAQ_JIRA_RAG__API_KEY = "your-key"
python -m nasdaq_jira --config config/config.yaml ask "Why did FIX Session disconnect?"
```

回答包含 executive summary、technical summary、action items、related issues、confidence 與 sources citations。

Answers include an executive summary, technical summary, action items, related issues, confidence, and source citations.

## Docker

```bash
docker compose run --rm crawler
```

請掛載 `storage_state.json`、`data/` 與 `logs/`；正式設定請先複製為 `config/config.yaml`。

Mount `storage_state.json`, `data/`, and `logs/` as volumes. Copy the example configuration to `config/config.yaml` for real use.

## 開發環境 / Development setup

專案目標為 Python 3.13。安裝 development dependencies、Chromium 與 pre-commit hooks：

The project targets Python 3.13. Install development dependencies, Chromium, and pre-commit hooks:

```bash
python -m pip install -e ".[dev]"
python -m playwright install chromium
pre-commit install
```

完整檢查 / Full validation:

```bash
pre-commit run --all-files
ruff check .
ruff format --check .
black --check .
mypy src
pytest
```

測試不會連線 Jira；整合測試應使用受控測試伺服器。

Tests do not contact Jira; integration tests should use a controlled test server.

### Make targets / Make 指令

| Target | 中文說明 | English description |
| --- | --- | --- |
| `make install` | 安裝專案、開發依賴與 Chromium | Install the project, dev dependencies, and Chromium |
| `make lint` | 執行 Ruff lint | Run Ruff lint checks |
| `make format` | 執行 Ruff format 與 Black | Run Ruff format and Black |
| `make typecheck` | 執行 MyPy | Run MyPy |
| `make test` | 執行 pytest | Run pytest |
| `make check` | 執行完整檢查 | Run lint, formatting, type checks, and tests |
| `make clean` | 清除快取與 build artifacts | Remove caches and build artifacts |