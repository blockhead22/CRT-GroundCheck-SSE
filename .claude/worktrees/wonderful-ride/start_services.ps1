#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Aether Service Manager -- starts, validates, monitors, and auto-restarts all services.

.DESCRIPTION
    Single entrypoint for the full Aether stack:
    1) Pre-flight checks (Python, venv, Ollama, disk space)
    2) Kill stale processes
    3) Start API server (crt_api.py)
    4) Start Telegram bot (optional)
    5) Monitor all services with health checks and auto-restart
    6) Log everything to ai_logs/service_manager.log

.PARAMETER NoClean
    Skip killing stale processes on startup.

.PARAMETER SkipTelegram
    Do not start the Telegram bot.

.PARAMETER NoMonitor
    Start services but do not run the health monitor loop.

.PARAMETER NoPortal
    Skip the interactive runtime portal (just run services + monitor).

.PARAMETER PortalManagesApi
    Let the runtime portal manage the API lifecycle.

.EXAMPLE
    .\start_services.ps1
    .\start_services.ps1 -SkipTelegram
    .\start_services.ps1 -NoPortal
#>

param(
    [switch]$NoClean,
    [switch]$SkipTelegram,  # kept for compat; Telegram is disabled by default (OpenClaw owns it)
    [switch]$Telegram,      # opt-in: explicitly start CRT's Telegram bot alongside OpenClaw
    [switch]$NoMonitor,
    [switch]$NoPortal,
    [switch]$PortalManagesApi
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

# ── Logging ──────────────────────────────────────────────────────────────────

$logDir = Join-Path $root "ai_logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
$logFile = Join-Path $logDir "service_manager.log"

function Write-Log {
    param([string]$Level, [string]$Msg)
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$ts] [$Level] $Msg"
    Add-Content -Path $logFile -Value $line -Encoding utf8
    switch ($Level) {
        "ERROR" { Write-Host $line -ForegroundColor Red }
        "WARN"  { Write-Host $line -ForegroundColor Yellow }
        "OK"    { Write-Host $line -ForegroundColor Green }
        default { Write-Host $line }
    }
}

function Write-Info($msg) { Write-Log "INFO" $msg }
function Write-Ok($msg)   { Write-Log "OK" $msg }
function Write-Warn($msg) { Write-Log "WARN" $msg }
function Write-Err($msg)  { Write-Log "ERROR" $msg }

Write-Info "═══════════════════════════════════════════════════════════════"
Write-Info "Aether Service Manager starting"
Write-Info "═══════════════════════════════════════════════════════════════"

# Telegram is now managed by OpenClaw. Disable it here unless explicitly requested.
if (-not $Telegram) {
    $SkipTelegram = $true
    Write-Info "Telegram: managed by OpenClaw (pass -Telegram to override)"
}

# ── Pre-flight Checks ────────────────────────────────────────────────────────

function Test-Preflight {
    $ok = $true

    # Python
    $python = Join-Path $root ".venv\Scripts\python.exe"
    if (Test-Path $python) {
        $pyVer = & $python --version 2>&1
        Write-Ok "Python: $pyVer (venv)"
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        $python = "python"
        $pyVer = & $python --version 2>&1
        Write-Warn "Python: $pyVer (system -- no venv found)"
    } else {
        Write-Err "Python not found"
        $ok = $false
    }
    $script:python = $python

    # Critical files
    foreach ($f in @("crt_api.py", "personal_agent/crt_rag.py", "routes/chat.py")) {
        if (-not (Test-Path (Join-Path $root $f))) {
            Write-Err "Missing critical file: $f"
            $ok = $false
        }
    }

    # Check key Python imports
    $importCheck = & $script:python -c "
import sys
errors = []
for mod in ['fastapi', 'uvicorn', 'sentence_transformers', 'numpy']:
    try:
        __import__(mod)
    except ImportError:
        errors.append(mod)
if errors:
    print('MISSING:' + ','.join(errors))
else:
    print('OK')
" 2>&1
    if ($importCheck -match "^MISSING:") {
        $missing = $importCheck -replace "^MISSING:", ""
        Write-Err "Missing Python packages: $missing"
        Write-Info "Run: pip install $($missing -replace ',', ' ')"
        $ok = $false
    } else {
        Write-Ok "Python dependencies: OK"
    }

    # Ollama (optional but recommended)
    if (Get-Command ollama -ErrorAction SilentlyContinue) {
        try {
            $ollamaList = & ollama list 2>&1
            Write-Ok "Ollama: available"
        } catch {
            Write-Warn "Ollama: installed but not responding"
        }
    } else {
        Write-Warn "Ollama: not found (local LLM generation will fail)"
    }

    # Disk space
    $drive = (Get-Item $root).PSDrive
    $freeGB = [math]::Round($drive.Free / 1GB, 1)
    if ($freeGB -lt 2) {
        Write-Warn "Low disk space: ${freeGB}GB free on $($drive.Name):"
    } else {
        Write-Ok "Disk space: ${freeGB}GB free"
    }

    # Telegram token (only relevant if -Telegram flag was passed)
    if (-not $SkipTelegram) {
        if ($env:TELEGRAM_BOT_TOKEN) {
            Write-Ok "Telegram token: set"
        } else {
            Write-Warn "TELEGRAM_BOT_TOKEN not set -- Telegram bot will not start"
            $script:SkipTelegram = $true
        }
    }

    return $ok
}

if (-not (Test-Preflight)) {
    Write-Err "Pre-flight checks failed. Fix the issues above before starting."
    exit 1
}

# ── Process Management ───────────────────────────────────────────────────────

function Stop-MatchingProcess([string]$name, [string]$pattern) {
    $procs = Get-CimInstance Win32_Process | Where-Object {
        $_.Name -eq $name -and ($_.CommandLine -match $pattern)
    }
    foreach ($p in $procs) {
        try {
            Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop
            Write-Info "Stopped $name PID=$($p.ProcessId)"
        } catch {
            Write-Warn "Could not stop PID=$($p.ProcessId): $($_.Exception.Message)"
        }
    }
}

if (-not $NoClean) {
    Write-Info "Cleaning stale service processes..."
    Stop-MatchingProcess -name "python.exe" -pattern "crt_api\.py|channels\.telegram_bot|tools[\\\/]runtime_portal\.py"
    Stop-MatchingProcess -name "powershell.exe" -pattern "start_api\.ps1|start_portal\.ps1"
    Start-Sleep -Seconds 1
}

# ── Environment ──────────────────────────────────────────────────────────────

if (-not $env:PORT) { $env:PORT = "8123" }
if (-not $env:CRT_HOST) { $env:CRT_HOST = "127.0.0.1" }
if (-not $env:CRT_CORS_ORIGINS) { $env:CRT_CORS_ORIGINS = "http://localhost:5173,http://localhost:5174,http://127.0.0.1:5173,http://127.0.0.1:5174" }
if (-not $env:CRT_SHARED_MEMORY) { $env:CRT_SHARED_MEMORY = "true" }
if (-not $env:CRT_ENABLE_LLM) { $env:CRT_ENABLE_LLM = "true" }
if (-not $env:CRT_OLLAMA_MODEL) { $env:CRT_OLLAMA_MODEL = "deepseek-r1:latest" }
if (-not $env:HF_HUB_OFFLINE) { $env:HF_HUB_OFFLINE = "1" }
if (-not $env:TRANSFORMERS_OFFLINE) { $env:TRANSFORMERS_OFFLINE = "1" }
$env:CRT_API_URL = "http://$($env:CRT_HOST):$($env:PORT)"

Write-Info "API URL: $($env:CRT_API_URL)"
Write-Info "Ollama model: $($env:CRT_OLLAMA_MODEL)"

# ── Service Startup ──────────────────────────────────────────────────────────

$services = @{}

function Start-Service-Api {
    Write-Info "Starting API server..."
    $apiLogFile = Join-Path $logDir "api_stdout.log"
    $apiErrFile = Join-Path $logDir "api_stderr.log"
    $proc = Start-Process -FilePath $python -ArgumentList "crt_api.py" `
        -WorkingDirectory $root -PassThru `
        -RedirectStandardOutput $apiLogFile `
        -RedirectStandardError $apiErrFile
    $services["api"] = @{
        Process = $proc
        Name = "API"
        StartTime = Get-Date
        Restarts = 0
        LogFile = $apiLogFile
        ErrFile = $apiErrFile
    }
    Write-Info "API PID=$($proc.Id)"
    return $proc
}

function Start-Service-Telegram {
    if ($SkipTelegram) { return $null }
    Write-Info "Starting Telegram bot..."
    $tgLogFile = Join-Path $logDir "telegram_stdout.log"
    $tgErrFile = Join-Path $logDir "telegram_stderr.log"
    $proc = Start-Process -FilePath $python -ArgumentList "-m", "channels.telegram_bot" `
        -WorkingDirectory $root -PassThru `
        -RedirectStandardOutput $tgLogFile `
        -RedirectStandardError $tgErrFile
    $services["telegram"] = @{
        Process = $proc
        Name = "Telegram"
        StartTime = Get-Date
        Restarts = 0
        LogFile = $tgLogFile
        ErrFile = $tgErrFile
    }
    Write-Info "Telegram PID=$($proc.Id)"
    return $proc
}

function Wait-ForHealth {
    param([string]$Url, [int]$TimeoutSeconds = 120)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $resp = Invoke-WebRequest -Uri "$Url/health" -UseBasicParsing -TimeoutSec 3
            if ($resp.StatusCode -eq 200) {
                return $true
            }
        } catch {
            Start-Sleep -Milliseconds 800
        }
    }
    return $false
}

# Start API
if (-not $PortalManagesApi) {
    Start-Service-Api
    Write-Info "Waiting for API health check..."
    if (Wait-ForHealth -Url $env:CRT_API_URL -TimeoutSeconds 120) {
        Write-Ok "API is healthy"
    } else {
        Write-Err "API failed to start within 120s"
        # Show last 20 lines of stderr for debugging
        $errFile = $services["api"].ErrFile
        if (Test-Path $errFile) {
            Write-Err "Last lines of API stderr:"
            Get-Content $errFile -Tail 20 | ForEach-Object { Write-Err "  $_" }
        }
        exit 1
    }
}

# Start Telegram only in standalone monitor mode.
# In portal mode, let tools/runtime_portal.py own the Telegram lifecycle.
if ($NoPortal) {
    Start-Service-Telegram
} elseif (-not $SkipTelegram) {
    Write-Info "Portal mode: runtime portal will start/manage Telegram bot."
}

Write-Ok "All services started"

# ── Health Monitor Loop ──────────────────────────────────────────────────────

function Show-Status {
    Write-Info "─── Service Status ───"
    foreach ($key in $services.Keys) {
        $svc = $services[$key]
        $proc = $svc.Process
        $status = if ($proc.HasExited) { "STOPPED (exit=$($proc.ExitCode))" } else { "RUNNING" }
        $uptime = if (-not $proc.HasExited) {
            $ts = (Get-Date) - $svc.StartTime
            "{0}h {1}m" -f [int]$ts.TotalHours, $ts.Minutes
        } else { "--" }
        $restarts = $svc.Restarts
        $color = if ($proc.HasExited) { "Red" } else { "Green" }
        Write-Host "  $($svc.Name): $status | uptime: $uptime | restarts: $restarts | PID: $($proc.Id)" -ForegroundColor $color
    }
    Write-Info "──────────────────────"
}

if ($NoMonitor -or $NoPortal -eq $false) {
    # If portal mode, hand off to the portal
    if (-not $NoPortal) {
        $portalArgs = @("tools/runtime_portal.py", "--api-url", $env:CRT_API_URL)
        if (-not $PortalManagesApi) {
            $portalArgs += "--skip-api"
        }
        if ($SkipTelegram) {
            $portalArgs += "--skip-telegram"
        }
        Write-Info "Handing off to runtime portal..."
        & $python @portalArgs
        # Portal exited -- clean up
        Write-Info "Portal exited. Stopping services..."
        foreach ($key in $services.Keys) {
            $proc = $services[$key].Process
            if (-not $proc.HasExited) {
                Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
                Write-Info "Stopped $($services[$key].Name) PID=$($proc.Id)"
            }
        }
        exit 0
    }
    if ($NoMonitor) {
        Show-Status
        Write-Info "NoMonitor set. Services running in background."
        exit 0
    }
}

# Standalone monitor mode (no portal)
Write-Info "Starting health monitor (check every 15s, Ctrl+C to stop)..."
Write-Info ""
Show-Status

$maxRestarts = 5
$checkInterval = 15

try {
    while ($true) {
        Start-Sleep -Seconds $checkInterval

        # Check API health
        if ($services.ContainsKey("api")) {
            $apiSvc = $services["api"]
            $apiProc = $apiSvc.Process

            if ($apiProc.HasExited) {
                Write-Err "API crashed (exit code: $($apiProc.ExitCode))"
                # Log crash details
                $errFile = $apiSvc.ErrFile
                if (Test-Path $errFile) {
                    $crashLines = Get-Content $errFile -Tail 30
                    $crashLines | ForEach-Object { Write-Err "  $_" }
                }

                if ($apiSvc.Restarts -lt $maxRestarts) {
                    $apiSvc.Restarts++
                    Write-Warn "Restarting API (attempt $($apiSvc.Restarts)/$maxRestarts)..."
                    Start-Service-Api
                    if (Wait-ForHealth -Url $env:CRT_API_URL -TimeoutSeconds 60) {
                        Write-Ok "API restarted successfully"
                    } else {
                        Write-Err "API failed to restart"
                    }
                } else {
                    Write-Err "API exceeded max restarts ($maxRestarts). Giving up."
                }
            } else {
                # Process alive -- verify health endpoint
                try {
                    $resp = Invoke-WebRequest -Uri "$($env:CRT_API_URL)/health" -UseBasicParsing -TimeoutSec 5
                    if ($resp.StatusCode -ne 200) {
                        Write-Warn "API health check returned $($resp.StatusCode)"
                    }
                } catch {
                    Write-Warn "API health check failed: $($_.Exception.Message)"
                }
            }
        }

        # Check Telegram
        if ($services.ContainsKey("telegram")) {
            $tgSvc = $services["telegram"]
            $tgProc = $tgSvc.Process

            if ($tgProc.HasExited) {
                Write-Err "Telegram bot crashed (exit code: $($tgProc.ExitCode))"
                $errFile = $tgSvc.ErrFile
                if (Test-Path $errFile) {
                    $crashLines = Get-Content $errFile -Tail 15
                    $crashLines | ForEach-Object { Write-Err "  $_" }
                }

                if ($tgSvc.Restarts -lt $maxRestarts) {
                    $tgSvc.Restarts++
                    Write-Warn "Restarting Telegram bot (attempt $($tgSvc.Restarts)/$maxRestarts)..."
                    Start-Service-Telegram
                    Write-Ok "Telegram bot restarted"
                } else {
                    Write-Err "Telegram bot exceeded max restarts ($maxRestarts). Giving up."
                }
            }
        }
    }
} finally {
    Write-Info "Shutting down services..."
    foreach ($key in $services.Keys) {
        $proc = $services[$key].Process
        if (-not $proc.HasExited) {
            Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
            Write-Info "Stopped $($services[$key].Name) PID=$($proc.Id)"
        }
    }
    Write-Ok "All services stopped. Logs in: $logDir"
}
