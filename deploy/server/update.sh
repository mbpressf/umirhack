#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/umirhack}"

cd "$APP_DIR"
git pull --ff-only
docker compose up -d --build
docker image prune -f

echo "Deployment updated successfully."
