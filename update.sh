#!/bin/bash
# The War Table — pull latest code, rebuild Docker image, restart container
# Run from the Unraid server: bash /mnt/user/appdata/gm-wiki/update.sh

set -e
cd "$(dirname "$0")"

echo "=== The War Table Update ==="
echo ""

echo "Pulling latest code from GitHub..."
git pull origin main
echo ""

echo "Stopping current container..."
docker compose down
echo ""

echo "Rebuilding and starting container..."
docker compose up -d --build
echo ""

echo "=== Update complete! ==="
echo "Tailing logs (Ctrl+C to exit)..."
echo ""
docker compose logs -f --tail=30
