#!/usr/bin/env pwsh
# Aether Runtime Portal (API + Telegram + unified logs + HMR)

if (-not $env:PORT) { $env:PORT = "8123" }
if (-not $env:CRT_HOST) { $env:CRT_HOST = "127.0.0.1" }
$env:CRT_API_URL = "http://$($env:CRT_HOST):$($env:PORT)"
if (-not $env:CRT_CORS_ORIGINS) { $env:CRT_CORS_ORIGINS = "http://localhost:5173,http://localhost:5174,http://127.0.0.1:5173,http://127.0.0.1:5174" }
if (-not $env:CRT_SHARED_MEMORY) { $env:CRT_SHARED_MEMORY = "true" }
if (-not $env:CRT_ENABLE_LLM) { $env:CRT_ENABLE_LLM = "true" }
if (-not $env:CRT_OLLAMA_MODEL) { $env:CRT_OLLAMA_MODEL = "qwen3:14b" }

Write-Host "Starting Aether Runtime Portal..."
Write-Host "- API URL: $env:CRT_API_URL"
Write-Host "- Host: $env:CRT_HOST"
Write-Host "- Port: $env:PORT"
Write-Host "- HMR: enabled"
Write-Host ""
Write-Host "Portal commands:"
Write-Host "  status | restart api | restart telegram | restart heartbeat | restart dnnt | quit"
Write-Host "  system status | system decay | system tick | system checks [limit]"
Write-Host "  system resolve <check_id> | system reinforce <memory_id> | system retrain"
Write-Host "  (copilot <...> still works as an alias)"
Write-Host ""

& .venv\Scripts\python.exe tools\runtime_portal.py --api-url $env:CRT_API_URL
