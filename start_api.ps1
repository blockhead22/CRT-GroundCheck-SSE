#!/usr/bin/env pwsh
# CRT API Server Startup Script

$env:PORT = "8123"
$env:CRT_SHARED_MEMORY = "true"
$env:CRT_ENABLE_LLM = "false"

Write-Host "Starting CRT API Server..."
Write-Host "- Port: $env:PORT"
Write-Host "- Shared Memory: $env:CRT_SHARED_MEMORY"
Write-Host "- LLM Extraction: $env:CRT_ENABLE_LLM"
Write-Host ""

& .venv\Scripts\python.exe crt_api.py
