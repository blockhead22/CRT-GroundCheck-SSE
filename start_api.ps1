#!/usr/bin/env pwsh
# CRT API Server Startup Script

$env:PORT = "8123"
$env:CRT_HOST = "127.0.0.1"  # Localhost only — change to 0.0.0.0 ONLY behind a reverse proxy
$env:CRT_CORS_ORIGINS = "http://localhost:5173,http://localhost:5174,http://127.0.0.1:5173,http://127.0.0.1:5174"
$env:CRT_SHARED_MEMORY = "true"
$env:CRT_ENABLE_LLM = "true"
$env:CRT_OLLAMA_MODEL = "deepseek-r1:latest"
if (-not $env:HF_HUB_OFFLINE) { $env:HF_HUB_OFFLINE = "1" }
if (-not $env:TRANSFORMERS_OFFLINE) { $env:TRANSFORMERS_OFFLINE = "1" }

Write-Host "Starting CRT API Server..."
Write-Host "- Host: $env:CRT_HOST"
Write-Host "- Port: $env:PORT"
Write-Host "- Shared Memory: $env:CRT_SHARED_MEMORY"
Write-Host "- LLM Extraction: $env:CRT_ENABLE_LLM"
Write-Host "- HF Offline: $env:HF_HUB_OFFLINE"
Write-Host ""

& .venv\Scripts\python.exe crt_api.py
