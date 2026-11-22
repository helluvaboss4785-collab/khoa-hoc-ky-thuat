@echo off
chcp 65001 >nul
setlocal
set "PY=%~dp0.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
"%PY%" "%~dp0scripts\dong_goi.py" --kiem-tra %*
set "ERR=%ERRORLEVEL%"
exit /b %ERR%
