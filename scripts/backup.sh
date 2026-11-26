#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname "$0")/backup-common.sh"

leave_stopped=false
if [[ "${1:-}" == "--leave-stopped" ]]; then
    leave_stopped=true
    shift
fi
[[ $# -le 1 ]] || { echo "Usage: $0 [--leave-stopped] [backup-directory]" >&2; exit 1; }
check_tools
backup_root="${1:-$PROJECT_ROOT/.backups}"
mkdir -p "$backup_root"
backup_root="$(cd "$backup_root" && pwd)"
backup="$(mktemp -d "$backup_root/lakehouse_backup_$(date +%Y%m%d_%H%M%S)_XXXXXX")"
chmod 700 "$backup"
volume_mapping > "$backup/volumes.tsv"
[[ -s "$backup/volumes.tsv" ]] || { echo "No Compose volumes found" >&2; exit 1; }
while IFS=$'\t' read -r key volume; do
    [[ "$key" =~ ^[a-zA-Z0-9_-]+$ && -n "$volume" ]] || { echo "Invalid volume mapping" >&2; exit 1; }
    docker volume inspect "$volume" >/dev/null
done < "$backup/volumes.tsv"

mapfile -t running_services < <(docker compose ps --status running --services)
[[ ${#running_services[@]} -gt 0 ]] || { echo "No running Compose services found" >&2; exit 1; }
printf '%s\n' "${running_services[@]}" > "$backup/running-services.txt"
restart_needed=false
cleanup() {
    local status=$?
    trap - EXIT
    if [[ "$restart_needed" == true ]]; then
        echo "Restarting previously running services..." >&2
        if ! docker compose start "${running_services[@]}"; then
            echo "ERROR: Failed to restart services; check docker compose ps." >&2
            status=1
        fi
    fi
    if [[ $status -ne 0 ]]; then
        rm -f "$backup/COMPLETE"
        echo "Backup failed; do not use $backup for recovery." >&2
    fi
    exit "$status"
}
trap cleanup EXIT

echo "Stopping Compose services; active jobs may be interrupted."
restart_needed=true
docker compose stop
while IFS=$'\t' read -r key volume; do
    check_volume_unused "$volume"
done < "$backup/volumes.tsv"

postgres_id="$(docker compose ps -aq postgres)"
[[ -n "$postgres_id" && "$(docker inspect -f '{{.State.ExitCode}}' "$postgres_id")" == 0 ]] || {
    echo "PostgreSQL did not stop cleanly; refusing backup." >&2
    exit 1
}

while IFS=$'\t' read -r key volume; do
    echo "Archiving $key ($volume)..."
    docker run --rm --network none --mount "type=volume,source=$volume,target=/source,readonly" \
        --entrypoint tar "$HELPER_IMAGE" -C /source -cpf - . | gzip > "$backup/$key.tar.gz"
    gzip -dc "$backup/$key.tar.gz" | tar -tf - >/dev/null
done < "$backup/volumes.tsv"

(
    cd "$backup"
    sha256sum volumes.tsv running-services.txt ./*.tar.gz > SHA256SUMS
)
touch "$backup/COMPLETE"
verify_backup "$backup"
echo "Verified backup: $backup"
if [[ "$leave_stopped" == true ]]; then
    restart_needed=false
    echo "Services remain stopped."
fi
