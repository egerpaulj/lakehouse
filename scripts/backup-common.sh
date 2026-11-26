#!/usr/bin/env bash

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"
HELPER_IMAGE="postgres:16-alpine"

volume_mapping() {
    docker compose config --format json | jq -er '
        .volumes | to_entries | sort_by(.key)[] |
        if (.value.external // false) or
           ((.value.driver // "local") != "local") or
           ((.value.driver_opts // {}) | length > 0)
        then error("only local Compose volumes without driver options are supported")
        else [.key, .value.name] | @tsv end'
}

check_tools() {
    for tool in docker jq gzip sha256sum tar diff; do
        command -v "$tool" >/dev/null || { echo "Missing required tool: $tool" >&2; return 1; }
    done
    docker image inspect "$HELPER_IMAGE" >/dev/null
}

check_volume_unused() {
    local volume="$1" containers
    containers="$(docker ps -q --filter "volume=$volume")"
    if [[ -n "$containers" ]]; then
        echo "Volume $volume is still mounted by running containers: $containers" >&2
        return 1
    fi
}

verify_backup() {
    local backup="$1" key volume
    [[ -f "$backup/COMPLETE" && -f "$backup/volumes.tsv" && -f "$backup/SHA256SUMS" ]] || {
        echo "Backup is incomplete or has an unsupported format: $backup" >&2
        return 1
    }
    (cd "$backup" && sha256sum volumes.tsv running-services.txt ./*.tar.gz | diff -u SHA256SUMS -)
    while IFS=$'\t' read -r key volume; do
        [[ "$key" =~ ^[a-zA-Z0-9_-]+$ && -n "$volume" && -f "$backup/$key.tar.gz" ]] || {
            echo "Invalid volume mapping or missing archive: $key" >&2
            return 1
        }
        gzip -dc "$backup/$key.tar.gz" | tar -tf - >/dev/null
    done < "$backup/volumes.tsv"
}
