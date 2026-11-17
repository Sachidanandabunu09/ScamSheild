#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
umask 077
TAG="$(cat .releases/current)"
export TAG
mkdir -p backups
file="backups/scamshield-$(date -u +%Y%m%dT%H%M%SZ).dump"
docker compose --project-name scamshield --env-file .env \
    -f ".releases/$TAG/compose.yml" exec -T db \
    pg_dump -U scam -d scamshield -Fc > "$file.tmp"
mv "$file.tmp" "$file"
echo "Backup created: $file"
echo "Copy it to a private location outside this EC2 instance."
