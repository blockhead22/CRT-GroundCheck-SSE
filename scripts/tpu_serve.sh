#!/usr/bin/env bash
# Runs ON the TPU VM (not your laptop).
# Installs vLLM with TPU backend and serves Qwen2.5-7B-Instruct on :8000.

set -euo pipefail

MODEL="Qwen/Qwen2.5-7B-Instruct"
PORT=8000
VENV=~/venv-aether

# Ensure venv tooling is present (fresh TPU images sometimes lack it).
if ! python3 -c "import ensurepip" 2>/dev/null; then
    sudo apt-get update -qq
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y python3-venv python3.10-venv
fi

if [ ! -d "$VENV" ]; then
    python3 -m venv "$VENV"
fi
source "$VENV/bin/activate"

pip install --upgrade pip
# vllm 0.19+ split TPU into tpu_inference. Try that path first; fall back to pinned 0.7.x with in-tree TPU.
pip install "vllm==0.10.0" tpu_inference "torch_xla[tpu]" \
    -f https://storage.googleapis.com/libtpu-releases/index.html \
    -f https://storage.googleapis.com/libtpu-wheels/index.html \
    || pip install "vllm==0.7.3" "transformers==4.48.3" "torch_xla[tpu]" \
    -f https://storage.googleapis.com/libtpu-releases/index.html \
    -f https://storage.googleapis.com/libtpu-wheels/index.html

export VLLM_USE_V1=1
export PJRT_DEVICE=TPU

exec python -m vllm.entrypoints.openai.api_server \
    --model "$MODEL" \
    --host 0.0.0.0 \
    --port "$PORT" \
    --tensor-parallel-size 4 \
    --max-model-len 8192 \
    --download-dir ~/.cache/huggingface
