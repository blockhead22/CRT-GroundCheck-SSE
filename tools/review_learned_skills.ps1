# Review and Approve Learned Skills
# Helps review session patterns detected by continuous learning skill

param(
    [switch]$Approve,
    [string]$SessionId
)

$LearnedSkillsPath = Join-Path $env:USERPROFILE ".claude\skills\learned"

if (-not (Test-Path $LearnedSkillsPath)) {
    Write-Host "No learned skills found at: $LearnedSkillsPath" -ForegroundColor Yellow
    exit 0
}

$sessionFiles = Get-ChildItem -Path $LearnedSkillsPath -Filter "session_*.json" | Sort-Object LastWriteTime -Descending

if ($sessionFiles.Count -eq 0) {
    Write-Host "No pending sessions to review" -ForegroundColor Gray
    exit 0
}

Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "LEARNED SKILLS REVIEW" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan

foreach ($file in $sessionFiles) {
    $session = Get-Content $file.FullName -Raw | ConvertFrom-Json
    
    if ($session.status -eq "approved") {
        continue
    }
    
    Write-Host "`nSession: $($session.timestamp)" -ForegroundColor White
    Write-Host "Messages: $($session.message_count)" -ForegroundColor Gray
    Write-Host "Patterns detected: $($session.patterns_detected.Count)" -ForegroundColor Yellow
    
    foreach ($pattern in $session.patterns_detected) {
        Write-Host "  [$($pattern.confidence.ToUpper())] $($pattern.type)" -ForegroundColor $(
            switch ($pattern.confidence) {
                "high" { "Green" }
                "medium" { "Yellow" }
                "low" { "Gray" }
                default { "White" }
            }
        )
        Write-Host "      $($pattern.context)" -ForegroundColor DarkGray
    }
    
    if ($Approve -and ($SessionId -eq $session.timestamp)) {
        $session.status = "approved"
        $session | ConvertTo-Json -Depth 10 | Set-Content $file.FullName
        Write-Host "`n  ✓ Session approved!" -ForegroundColor Green
    }
}

Write-Host "`n" + ("=" * 80) -ForegroundColor Cyan
Write-Host "Total pending sessions: $(($sessionFiles | Where-Object { (Get-Content $_.FullName | ConvertFrom-Json).status -eq 'pending_review' }).Count)" -ForegroundColor White
Write-Host "`nTo approve a session:" -ForegroundColor Yellow
Write-Host "  .\tools\review_learned_skills.ps1 -Approve -SessionId YYYYMMDD_HHMMSS" -ForegroundColor Gray
Write-Host "`nTo clear all pending:" -ForegroundColor Yellow
Write-Host "  Remove-Item '$LearnedSkillsPath\session_*.json'" -ForegroundColor Gray
