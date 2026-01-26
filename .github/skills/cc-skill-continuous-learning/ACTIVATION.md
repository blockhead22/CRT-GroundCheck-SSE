# Continuous Learning Skill - Activation Instructions

## What This Skill Does

Automatically analyzes your coding sessions to extract reusable patterns, debugging techniques, and project-specific knowledge.

## How It Works

1. **Runs at session end** - Analyzes conversation transcripts when you stop working
2. **Detects patterns** - Identifies error resolutions, debugging approaches, workarounds
3. **Saves summaries** - Stores session insights to `~/.claude/skills/learned/`
4. **Review & approve** - You decide which patterns to keep as learned skills

## Activation Steps

### Option 1: Manual Testing (No Hook Required)

Test the skill directly on any session transcript:

```powershell
# Test on a hypothetical transcript
.\AI_round2\.agents\skills\cc-skill-continuous-learning\evaluate-session.ps1 -TranscriptPath "path\to\transcript.json"
```

### Option 2: VS Code Task (Recommended for Windows)

Add to `.vscode/tasks.json`:

```json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "Evaluate Session for Learning",
      "type": "shell",
      "command": "powershell",
      "args": [
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        "${workspaceFolder}/.agents/skills/cc-skill-continuous-learning/evaluate-session.ps1"
      ],
      "presentation": {
        "reveal": "always",
        "panel": "new"
      },
      "problemMatcher": []
    }
  ]
}
```

Then run: **Terminal > Run Task > Evaluate Session for Learning**

### Option 3: GitHub Copilot Agent (If Using Copilot)

The skill follows the `.agents/` convention used by GitHub Copilot agents. If you're using Copilot in VS Code, it may automatically discover and use this skill.

### Option 4: Post-Session Script

Add to your workflow as a manual step after significant coding sessions:

```powershell
# Create alias in PowerShell profile
Set-Alias -Name learn -Value "D:\AI_round2\.agents\skills\cc-skill-continuous-learning\evaluate-session.ps1"

# Then run after sessions
learn -TranscriptPath $env:LAST_SESSION_TRANSCRIPT
```

## Configuration

Edit [config.json](.agents/skills/cc-skill-continuous-learning/config.json):

```json
{
  "min_session_length": 10,        // Minimum messages to analyze
  "extraction_threshold": "medium", // Sensitivity: low/medium/high
  "auto_approve": false,           // Require manual review
  "learned_skills_path": "~/.claude/skills/learned/",
  "patterns_to_detect": [
    "error_resolution",
    "user_corrections",
    "workarounds",
    "debugging_techniques",
    "project_specific"
  ]
}
```

## Review Learned Skills

After sessions are analyzed:

```powershell
# Review pending patterns
.\tools\review_learned_skills.ps1

# Approve a specific session
.\tools\review_learned_skills.ps1 -Approve -SessionId 20260126_143022
```

## Current Status

- ✅ PowerShell version created: `evaluate-session.ps1`
- ✅ Review tool created: `tools/review_learned_skills.ps1`
- ⏭️ Manual testing available (no automatic hook yet)
- ⏭️ Requires Claude Code transcript access for full automation

## Pattern Detection

The skill currently detects:

| Pattern | Trigger Keywords | Confidence |
|---------|-----------------|------------|
| Error Resolution | error, exception, failed, traceback | Medium |
| Debugging | debug, trace, print, breakpoint | Low |
| Workarounds | workaround, alternative, instead, fix | Medium |
| CRT Project | crt, contradiction, memory, ledger | High |

## Limitations

- Requires access to session transcripts (not always available in VS Code)
- Pattern detection is keyword-based (could be enhanced with LLM analysis)
- No automatic hook integration for VS Code on Windows yet

## Next Steps

Would you like to:
1. Test the skill manually on a sample conversation?
2. Set up a VS Code task to run it on-demand?
3. Enhance pattern detection with more sophisticated analysis?
