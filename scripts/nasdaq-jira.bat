@echo off
setlocal

set "ROOT=%~dp0.."
pushd "%ROOT%" || exit /b 1

if "%~1"=="" goto usage
if "%~1"=="login" goto check_config
if "%~1"=="crawl" goto check_config
if "%~1"=="sync" goto check_config
if "%~1"=="incremental" goto check_config
if "%~1"=="sync-full" goto check_config
if "%~1"=="sync-resume" goto check_config
if "%~1"=="ask" goto check_config
if "%~1"=="show" goto check_config
goto usage

:check_config
if not exist "config\config.yaml" (
    echo Missing config\config.yaml.
    echo Copy config\config.example.yaml to config\config.yaml and update it first.
    popd
    exit /b 1
)

if exist ".venv\Scripts\python.exe" (
    set "PYTHON=.venv\Scripts\python.exe"
) else (
    set "PYTHON=python"
)

if "%~1"=="login" goto login
if "%~1"=="crawl" goto crawl
if "%~1"=="sync" goto sync
if "%~1"=="incremental" goto sync
if "%~1"=="sync-full" goto sync_full
if "%~1"=="sync-resume" goto sync_resume
if "%~1"=="ask" goto ask
if "%~1"=="show" goto show
goto usage

:login
"%PYTHON%" -m nasdaq_jira --config config\config.yaml --login
set "EXIT_CODE=%ERRORLEVEL%"
goto done

:crawl
"%PYTHON%" -m nasdaq_jira --config config\config.yaml
set "EXIT_CODE=%ERRORLEVEL%"
goto done

:sync
"%PYTHON%" -m nasdaq_jira --config config\config.yaml sync --incremental %~2
set "EXIT_CODE=%ERRORLEVEL%"
goto done

:sync_full
"%PYTHON%" -m nasdaq_jira --config config\config.yaml sync --full %~2
set "EXIT_CODE=%ERRORLEVEL%"
goto done

:sync_resume
"%PYTHON%" -m nasdaq_jira --config config\config.yaml sync --resume %~2
set "EXIT_CODE=%ERRORLEVEL%"
goto done

:ask
if "%~2"=="" (
    echo Usage: scripts\nasdaq-jira.bat ask "Your question"
    set "EXIT_CODE=2"
    goto done
)
"%PYTHON%" -m nasdaq_jira --config config\config.yaml ask "%~2"
set "EXIT_CODE=%ERRORLEVEL%"
goto done

:show
if "%~2"=="" (
    echo Usage: scripts\nasdaq-jira.bat show ISSUE-KEY
    set "EXIT_CODE=2"
    goto done
)
if /I "%~3"=="--all-comments" goto show_all
"%PYTHON%" -m nasdaq_jira --config config\config.yaml show "%~2"
set "EXIT_CODE=%ERRORLEVEL%"
goto done
:show_all
"%PYTHON%" -m nasdaq_jira --config config\config.yaml show "%~2" --all-comments
set "EXIT_CODE=%ERRORLEVEL%"
goto done

:usage
echo Usage:
echo   scripts\nasdaq-jira.bat login       - Login to Jira and save the browser session
echo   scripts\nasdaq-jira.bat crawl       - Crawl the issue list and save issues
echo   scripts\nasdaq-jira.bat sync [ISSUE-KEY] - Run incremental synchronization
echo   scripts\nasdaq-jira.bat incremental - Run incremental synchronization
echo   scripts\nasdaq-jira.bat sync-full   - Run a full synchronization
echo   scripts\nasdaq-jira.bat sync-resume [ISSUE-KEY] - Resume an interrupted synchronization
echo   scripts\nasdaq-jira.bat ask "Your question" - Ask the Jira AI knowledge base
echo   scripts\nasdaq-jira.bat show ISSUE-KEY - Display a stored Jira issue and comment summaries
echo     Add --all-comments to display every stored comment
set "EXIT_CODE=2"

:done
popd
exit /b %EXIT_CODE%