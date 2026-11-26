#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname "$0")/backup-common.sh"

[[ $# -eq 1 ]] || { echo "Usage: $0 BACKUP_PATH" >&2; exit 1; }
check_tools
backup="$(cd "$1" && pwd)"
verify_backup "$backup"
if ! diff -u "$backup/volumes.tsv" <(volume_mapping); then
    echo "Compose volume mapping differs from the backup; refusing restore." >&2
    exit 1
fi

project="$(docker compose config --format json | jq -er '.name')"
while IFS=$'\t' read -r key volume; do
    if ! docker volume inspect "$volume" >/dev/null 2>&1; then
        docker volume create --label "com.docker.compose.project=$project" \
            --label "com.docker.compose.volume=$key" "$volume" >/dev/null
    fi
    check_volume_unused "$volume"
    if ! docker run --rm --network none --mount "type=volume,source=$volume,target=/target,readonly" \
        --entrypoint sh "$HELPER_IMAGE" -c 'test -z "$(find /target -mindepth 1 -maxdepth 1 -print -quit)"'; then
        echo "Volume $volume is not empty; refusing to overwrite it." >&2
        exit 1
    fi
done < "$backup/volumes.tsv"

while IFS=$'\t' read -r key volume; do
    echo "Restoring $key ($volume)..."
    gzip -dc "$backup/$key.tar.gz" | docker run --rm -i --network none \
        --mount "type=volume,source=$volume,target=/target" --entrypoint tar \
        "$HELPER_IMAGE" -C /target --numeric-owner -xpf -
done < "$backup/volumes.tsv"
echo "Restore complete. Start services with: docker compose up -d"
