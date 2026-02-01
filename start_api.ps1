#!/usr/bin/env pwsh
# CRT API Server Startup Script

$env:PORT = "8123"
$env:CRT_HOST = "0.0.0.0"  # Listen on all interfaces for external access
$env:CRT_CORS_ORIGINS = "*"  # Allow all origins for external access
$env:CRT_SHARED_MEMORY = "true"
$env:CRT_ENABLE_LLM = "true"
$env:CRT_OLLAMA_MODEL = "deepseek-r1:latest"

Write-Host "Starting CRT API Server..."
Write-Host "- Host: $env:CRT_HOST"
Write-Host "- Port: $env:PORT"
Write-Host "- Shared Memory: $env:CRT_SHARED_MEMORY"
Write-Host "- LLM Extraction: $env:CRT_ENABLE_LLM"
Write-Host ""

& .venv\Scripts\python.exe crt_api.py
