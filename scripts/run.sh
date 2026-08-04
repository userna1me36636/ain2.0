#!/usr/bin/env bash
set -euo pipefail
if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "Created .env. Add your Discord token before running again."
  exit 1
fi
python3.12 -m bot
