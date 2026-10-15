@echo off
rem Refresh data\mentions.js for index.html, then open the app.
cd /d "%~dp0"
if not exist .venv (
    python -m venv .venv
    .venv\Scripts\python -m pip install -q -r requirements.txt
)
set PYTHONIOENCODING=utf-8
.venv\Scripts\python -m trpa_monitor %*
start "" index.html
pause
