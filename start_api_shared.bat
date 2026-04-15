@echo off
REM Start the Aether backend with shared-memory mode enabled.
REM All threads route to crt_memory_shared.db (the rich corpus).

set CRT_SHARED_MEMORY=true
echo [start_api_shared] CRT_SHARED_MEMORY=true
echo [start_api_shared] Starting Aether API on http://127.0.0.1:8000
echo.

"%~dp0.venv\Scripts\python.exe" "%~dp0crt_api.py"
