#!/usr/bin/env bash
# D2 — TPU spin-up for Aether Bench v0 (small-brain tier).
#
# DRY SCRIPT: read end-to-end before running. Every gcloud call is a real
# action in your `aeteros` project. None of it is destructive on its own,
# but the VM will accrue persistent-disk cost the moment it exists.
#
# Assumes:
#   - `gcloud auth login` already done, and `gcloud config set project aeteros`
#   - TRC free-quota letter (2026-04-10) is still active
#   - You are OK with spot preemption (this script uses --spot)
#
# What this creates:
#   - 1 x TPU v5e-8 VM named aether-tpu-1 in europe-west4-b (TRC-free zone)
#   - Attached boot disk ~150 GB pd-balanced (Qwen2.5-7B weights ≈ 15 GB)
#   - Firewall rule allowing your local IP to reach port 8000 of the VM
#
# Next script: tpu_serve.sh runs ON the VM to install + start vLLM.

set -euo pipefail

PROJECT=aeteros
ZONE=europe-west4-b
TPU_NAME=aether-tpu-1
ACCELERATOR=v5litepod-8        # v5e 8-chip pod slice
RUNTIME=v2-alpha-tpuv5-lite    # Google-recommended runtime for v5e
DISK_SIZE=150
MY_IP="$(curl -s ifconfig.me)"  # your public IP for firewall rule
SERVE_PORT=8000

echo ">>> Project / zone / TPU: $PROJECT / $ZONE / $TPU_NAME"
echo ">>> Local IP for firewall whitelist: $MY_IP"
echo ">>> Accelerator: $ACCELERATOR  Runtime: $RUNTIME  Disk: ${DISK_SIZE}GB"
echo
read -p "Proceed? [y/N] " ok
[[ "$ok" == "y" || "$ok" == "Y" ]] || { echo "aborted."; exit 1; }

# 1. Create the TPU VM (spot, TRC-free under europe-west4-b v5e quota).
gcloud compute tpus tpu-vm create "$TPU_NAME" \
    --zone="$ZONE" \
    --accelerator-type="$ACCELERATOR" \
    --version="$RUNTIME" \
    --spot \
    --data-disk="source=projects/$PROJECT/zones/$ZONE/disks/${TPU_NAME}-data,mode=read-write" 2>/dev/null || \
gcloud compute tpus tpu-vm create "$TPU_NAME" \
    --zone="$ZONE" \
    --accelerator-type="$ACCELERATOR" \
    --version="$RUNTIME" \
    --spot

# 2. Firewall rule: only our IP can hit port 8000.
gcloud compute firewall-rules create aether-tpu-serve \
    --direction=INGRESS \
    --action=ALLOW \
    --rules=tcp:"$SERVE_PORT" \
    --source-ranges="${MY_IP}/32" \
    --target-tags=aether-tpu || echo "(firewall rule may already exist — continuing)"

gcloud compute tpus tpu-vm add-tags "$TPU_NAME" \
    --zone="$ZONE" --tags=aether-tpu || true

# 3. Print the external IP so you can wire it into the harness.
echo
echo ">>> TPU created. External IP:"
gcloud compute tpus tpu-vm describe "$TPU_NAME" --zone="$ZONE" \
    --format='value(networkEndpoints[0].accessConfig.externalIp)'

echo
echo ">>> Next:"
echo "  1. scp scripts/tpu_serve.sh to the VM:"
echo "     gcloud compute tpus tpu-vm scp scripts/tpu_serve.sh $TPU_NAME:~/ --zone=$ZONE"
echo "  2. SSH in and run it:"
echo "     gcloud compute tpus tpu-vm ssh $TPU_NAME --zone=$ZONE --command='bash ~/tpu_serve.sh'"
echo "  3. Set TPU_BRAIN_URL=http://<external-ip>:$SERVE_PORT/v1 in your local env"
echo "  4. python -m labs.aether_bench.harness --brain tpu_qwen7b --arm both"
echo
echo ">>> Shutdown when done (stops disk billing):"
echo "  gcloud compute tpus tpu-vm delete $TPU_NAME --zone=$ZONE"
