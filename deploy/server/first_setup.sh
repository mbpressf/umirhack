#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/mbpressf/umirhack.git}"
APP_DIR="${APP_DIR:-/opt/umirhack}"

apt-get update
apt-get install -y ca-certificates curl git docker.io docker-compose-plugin
systemctl enable --now docker

if [ ! -d "$APP_DIR/.git" ]; then
  git clone "$REPO_URL" "$APP_DIR"
fi

cd "$APP_DIR"

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example. Fill VK_API_TOKEN if needed."
fi

docker compose up -d --build

echo "Initial deployment completed. App should be available on port ${APP_PORT:-80}."
