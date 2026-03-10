#!/usr/bin/env pwsh
<#
Single entrypoint to start Aether services cleanly.

Default behavior:
1) Kill stale API/portal/telegram processes from this repo
2) Start API (crt_api.py) in background
3) Wait for /health on 127.0.0.1:8123
4) Start runtime portal in --skip-api mode (avoids port bind loops)

Usage:
  .\start_services.ps1
  .\start_services.ps1 -NoClean
  .\start_services.ps1 -PortalManagesApi
  .\start_services.ps1 -SkipTelegram
  .\start_services.ps1 -NoPortal
#>

param(
    [switch]$NoClean,
    [switch]$PortalManagesApi,
    [switch]$SkipTelegram,
    [switch]$NoPortal
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

function Write-Info($msg) {
    Write-Host "[start-services] $msg"
}

function Stop-MatchingProcess([string]$name, [string]$pattern) {
    $procs = Get-CimInstance Win32_Process | Where-Object {
        $_.Name -eq $name -and ($_.CommandLine -match $pattern)
    }
    foreach ($p in $procs) {
        try {
            Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop
            Write-Info "Stopped $name PID=$($p.ProcessId)"
        } catch {
            Write-Info "Could not stop PID=$($p.ProcessId): $($_.Exception.Message)"
        }
    }
}

if (-not $NoClean) {
    Write-Info "Cleaning stale service processes..."
    Stop-MatchingProcess -name "python.exe" -pattern "crt_api\.py|channels\.telegram_bot|tools[\\\/]runtime_portal\.py"
    Stop-MatchingProcess -name "powershell.exe" -pattern "start_api\.ps1|start_portal\.ps1|start_services\.ps1"
}

# Shared env defaults
if (-not $env:PORT) { $env:PORT = "8123" }
if (-not $env:CRT_HOST) { $env:CRT_HOST = "127.0.0.1" }
if (-not $env:CRT_CORS_ORIGINS) { $env:CRT_CORS_ORIGINS = "http://localhost:5173,http://localhost:5174,http://127.0.0.1:5173,http://127.0.0.1:5174" }
if (-not $env:CRT_SHARED_MEMORY) { $env:CRT_SHARED_MEMORY = "true" }
if (-not $env:CRT_ENABLE_LLM) { $env:CRT_ENABLE_LLM = "true" }
if (-not $env:CRT_OLLAMA_MODEL) { $env:CRT_OLLAMA_MODEL = "deepseek-r1:latest" }
if (-not $env:HF_HUB_OFFLINE) { $env:HF_HUB_OFFLINE = "1" }
if (-not $env:TRANSFORMERS_OFFLINE) { $env:TRANSFORMERS_OFFLINE = "1" }
$env:CRT_API_URL = "http://$($env:CRT_HOST):$($env:PORT)"

$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = "python"
}

if (-not $PortalManagesApi) {
    Write-Info "Starting API in background on $($env:CRT_API_URL)..."
    $apiProc = Start-Process -FilePath $python -ArgumentList "crt_api.py" -WorkingDirectory $root -PassThru
    Write-Info "API PID=$($apiProc.Id)"

    $deadline = (Get-Date).AddSeconds(120)
    $apiUp = $false
    while ((Get-Date) -lt $deadline) {
        try {
            $resp = Invoke-WebRequest -Uri "$($env:CRT_API_URL)/health" -UseBasicParsing -TimeoutSec 3
            if ($resp.StatusCode -eq 200) {
                $apiUp = $true
                break
            }
        } catch {
            Start-Sleep -Milliseconds 800
        }
    }
    if (-not $apiUp) {
        throw "API did not become healthy at $($env:CRT_API_URL)/health within timeout."
    }
    Write-Info "API health check passed."
}

if ($NoPortal) {
    Write-Info "NoPortal set; leaving API running."
    exit 0
}

$portalArgs = @("tools/runtime_portal.py", "--api-url", $env:CRT_API_URL)
if (-not $PortalManagesApi) {
    $portalArgs += "--skip-api"
}
if ($SkipTelegram) {
    $portalArgs += "--skip-telegram"
}

Write-Info "Starting portal with args: $($portalArgs -join ' ')"
& $python @portalArgs
