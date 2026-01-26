# Continuous Learning - Session Evaluator (PowerShell)
# Runs on Stop hook to extract reusable patterns from Claude Code sessions
#
# Hook config (add to VS Code settings.json or Claude settings):
# {
#   "claude.hooks": {
#     "Stop": [{
#       "matcher": "*",
#       "hooks": [{
#         "type": "command",
#         "command": "powershell -ExecutionPolicy Bypass -File .agents/skills/cc-skill-continuous-learning/evaluate-session.ps1"
#       }]
#     }]
#   }
# }

param(
    [string]$TranscriptPath = $env:CLAUDE_TRANSCRIPT_PATH
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ConfigFile = Join-Path $ScriptDir "config.json"
$LearnedSkillsPath = Join-Path $env:USERPROFILE ".claude\skills\learned"
$MinSessionLength = 10

# Load config if exists
if (Test-Path $ConfigFile) {
    $config = Get-Content $ConfigFile -Raw | ConvertFrom-Json
    $MinSessionLength = $config.min_session_length
    $LearnedSkillsPath = $config.learned_skills_path -replace '~', $env:USERPROFILE
}

# Ensure learned skills directory exists
New-Item -ItemType Directory -Force -Path $LearnedSkillsPath | Out-Null

# Check transcript path
if (-not $TranscriptPath -or -not (Test-Path $TranscriptPath)) {
    Write-Host "[ContinuousLearning] No transcript path provided" -ForegroundColor Yellow
    exit 0
}

# Count messages in session
$transcriptContent = Get-Content $TranscriptPath -Raw
$userMessages = $transcriptContent | Select-String -Pattern '"type"\s*:\s*"user"' -AllMatches
$messageCount = if ($userMessages) { $userMessages.Matches.Count } else { 0 }

# Skip short sessions
if ($messageCount -lt $MinSessionLength) {
    Write-Host "[ContinuousLearning] Session too short ($messageCount messages), skipping" -ForegroundColor Gray
    exit 0
}

Write-Host "[ContinuousLearning] Session has $messageCount messages - evaluating for extractable patterns" -ForegroundColor Cyan
Write-Host "[ContinuousLearning] Save learned skills to: $LearnedSkillsPath" -ForegroundColor Cyan

# Extract session metadata
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$sessionFile = Join-Path $LearnedSkillsPath "session_$timestamp.json"

# Create session summary
$sessionSummary = @{
    timestamp = $timestamp
    message_count = $messageCount
    transcript_path = $TranscriptPath
    patterns_detected = @()
    status = "pending_review"
}

# Simple pattern detection (can be enhanced with AI analysis)
$patterns = @()

# Detect error resolutions
if ($transcriptContent -match "(?i)(error|exception|failed|traceback)") {
    $patterns += @{
        type = "error_resolution"
        confidence = "medium"
        context = "Session contained error handling and resolution"
    }
}

# Detect debugging techniques
if ($transcriptContent -match "(?i)(debug|trace|print|console\.log|breakpoint)") {
    $patterns += @{
        type = "debugging_techniques"
        confidence = "low"
        context = "Session used debugging approaches"
    }
}

# Detect workarounds
if ($transcriptContent -match "(?i)(workaround|alternative|instead|fix)") {
    $patterns += @{
        type = "workarounds"
        confidence = "medium"
        context = "Session developed workarounds or alternative solutions"
    }
}

# Detect project-specific patterns
if ($transcriptContent -match "(?i)(crt|contradiction|memory|ledger|groundcheck)") {
    $patterns += @{
        type = "project_specific"
        confidence = "high"
        context = "Session worked on CRT Memory project-specific code"
    }
}

$sessionSummary.patterns_detected = $patterns

# Save session summary
$sessionSummary | ConvertTo-Json -Depth 10 | Set-Content $sessionFile

Write-Host "[ContinuousLearning] Session summary saved to: $sessionFile" -ForegroundColor Green
Write-Host "[ContinuousLearning] Detected $($patterns.Count) potential patterns:" -ForegroundColor Green

foreach ($pattern in $patterns) {
    Write-Host "  - $($pattern.type) (confidence: $($pattern.confidence))" -ForegroundColor White
}

if ($patterns.Count -gt 0) {
    Write-Host "`n[ContinuousLearning] Review and approve patterns to add to learned skills" -ForegroundColor Yellow
    Write-Host "[ContinuousLearning] Run: .\tools\review_learned_skills.ps1" -ForegroundColor Yellow
}

exit 0
