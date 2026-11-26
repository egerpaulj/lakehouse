#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname "$0")/backup-common.sh"

[[ $# -eq 1 ]] || { echo "Usage: $0 BACKUP_PATH" >&2; exit 1; }
check_tools
backup="$(cd "$1" && pwd)"
verify_backup "$backup"
echo "Backup checksums and archive structure verified."
