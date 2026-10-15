@echo off
rem Unattended daily refresh of data\ (for Task Scheduler; see schedule_daily.ps1).
rem Unlike update_data.bat it doesn't open the app or wait for a key press, and it writes
rem a log to logs\update_YYYY-MM-DD.log.
rem
rem   run_daily.bat            refresh data\ only
rem   run_daily.bat publish    also commit data\ and push it, so GitHub Pages updates
cd /d "%~dp0"
if not exist logs mkdir logs
for /f %%d in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"') do set TODAY=%%d
set LOG=logs\update_%TODAY%.log
set PYTHONIOENCODING=utf-8

if not exist .venv (
    python -m venv .venv
    .venv\Scripts\python -m pip install -q -r requirements.txt
)
echo ==== %DATE% %TIME% ==== > "%LOG%"
.venv\Scripts\python -m trpa_monitor >> "%LOG%" 2>&1
set RESULT=%ERRORLEVEL%
if not "%RESULT%"=="0" (
    echo Collector exited with %RESULT%; not publishing. >> "%LOG%"
    exit /b %RESULT%
)

if /i "%~1"=="publish" (
    git add data >> "%LOG%" 2>&1
    git diff --cached --quiet -- data && (echo No data changes to publish. >> "%LOG%") || (
        git commit -m "Daily TRPA mention data refresh %TODAY%" -- data >> "%LOG%" 2>&1
        git push >> "%LOG%" 2>&1
    )
)

rem Keep the last 30 days of logs.
forfiles /p logs /m update_*.log /d -30 /c "cmd /c del @path" >nul 2>&1
exit /b 0
