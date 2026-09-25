#!/usr/bin/env bash
# Push the pinecone_bot/ deterministic stack to the Raspberry Pi.
#
# Run FROM THE LAPTOP (or any dev machine with the repo checked out), from
# the repo root:
#     bash deploy/push_to_pi.sh
#
# Copies: pinecone_bot/, tools/, motions/, tests/, requirements-pinecone.txt
# and pinecone_config.json (if it exists locally). Uses rsync when
# available (fast, deletes files removed locally, resumable); falls back to
# scp -r otherwise (plain copy, no delete).
#
# Config via env vars:
#     PI_HOST   ssh target, default "pi@raspberrypi.local"
#     PI_DIR    remote repo dir, default "~/hackaton"
#
# Examples:
#     PI_HOST=robot@192.168.1.42 bash deploy/push_to_pi.sh
#     PI_HOST=pi@raspberrypi.local PI_DIR=~/hackaton bash deploy/push_to_pi.sh
#
# This script does NOT run deploy/setup_pi.sh or install anything on the
# Pi - it only copies files. Run the printed next command on the Pi
# afterwards.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PI_HOST="${PI_HOST:-pi@raspberrypi.local}"
PI_DIR="${PI_DIR:-~/hackaton}"

step() { printf '\n==> %s\n' "$*"; }

cd "$REPO_DIR"

ITEMS=(pinecone_bot tools motions tests requirements-pinecone.txt)
if [[ -f pinecone_config.json ]]; then
  ITEMS+=(pinecone_config.json)
else
  echo "Note: no local pinecone_config.json - skipping (Pi keeps its own if it has one)."
fi

step "Target: $PI_HOST:$PI_DIR"

if command -v rsync >/dev/null 2>&1; then
  step "Copying with rsync"
  ssh "$PI_HOST" "mkdir -p $PI_DIR"
  rsync -avz --progress \
    --exclude '.venv' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude 'frames/' \
    "${ITEMS[@]}" \
    "$PI_HOST:$PI_DIR/"
else
  step "rsync not found, falling back to scp -r (no delete, no exclude filters"
  echo "    - remove stray .venv/__pycache__/frames/ on the Pi by hand if needed)"
  ssh "$PI_HOST" "mkdir -p $PI_DIR"
  for item in "${ITEMS[@]}"; do
    scp -r "$item" "$PI_HOST:$PI_DIR/"
  done
fi

step "Done"
echo "Next, on the Pi:"
echo "    ssh $PI_HOST"
echo "    cd $PI_DIR"
echo "    uv pip install --python .venv/bin/python -r requirements-pi.txt"
echo "    python -m pinecone_bot.main --dry-run --show"
