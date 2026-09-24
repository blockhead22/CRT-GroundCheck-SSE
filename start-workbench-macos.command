#!/bin/zsh
set -e
cd -- "${0:A:h}"
export PATH="$HOME/.grok/bin:/opt/homebrew/bin:$PATH"
export AETHER_PYTHON="$PWD/.venv-macos/bin/python"
export AETHER_GROK_BUILD_BIN="$HOME/.grok/bin/grok"
export AETHER_GROK_MODEL="grok-4.7"
export AETHER_GROK_SHADOW_HOME="$HOME/.aether/grok-workbench"
export PYTHONDONTWRITEBYTECODE=1
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
cd workbench
exec npm run dev
