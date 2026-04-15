#!/usr/bin/env pwsh
# Start the Aether backend with shared-memory mode enabled.
# All threads route to crt_memory_shared.db (the rich 1000+ memory corpus).
# Use this when running the backend for MCP / standalone use, instead of
# the full Electron startup.

$env:CRT_SHARED_MEMORY = "true"
Write-Host "[start_api_shared] CRT_SHARED_MEMORY=true — all threads use crt_memory_shared.db"
Write-Host "[start_api_shared] Starting Aether API on http://127.0.0.1:8000"
Write-Host ""

& "$PSScriptRoot\.venv\Scripts\python.exe" "$PSScriptRoot\crt_api.py"
