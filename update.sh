#!/bin/bash
# The War Table — pull latest code, rebuild Docker image, restart container
# Run from Unraid: bash /mnt/user/appdata/gm-wiki/update.sh
# Perfect for 10+ daily test builds

set -euo pipefail

cd "$(dirname "$0")"

# Colors for nice Unraid terminal output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}=== The War Table Update ===${NC}\n"

echo -e "${YELLOW}1. Pulling latest code from GitHub...${NC}"
git fetch origin
git reset --hard origin/main
git clean -fd
echo -e "${GREEN}✓ Code updated${NC}\n"

echo -e "${YELLOW}2. Stopping container + removing old image...${NC}"
docker compose down --rmi local --remove-orphans
echo -e "${GREEN}✓ Stopped & old image removed${NC}\n"

echo -e "${YELLOW}3. Pulling latest base images + rebuilding...${NC}"
docker compose build --pull
docker compose up -d --force-recreate
echo -e "${GREEN}✓ Rebuilt and started${NC}\n"

echo -e "${YELLOW}4. Cleaning up old images & build cache (saves tons of space)...${NC}"
docker image prune -f
docker builder prune -f
echo -e "${GREEN}✓ Cleanup complete${NC}\n"

echo -e "${GREEN}=== Update complete! ===${NC}"
echo ""
echo "Tailing logs (Ctrl+C to exit)..."
echo ""
docker compose logs -f --tail=40