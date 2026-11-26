# Offline backup and restore

The scripts archive all named volumes declared by the current Compose
configuration, including the PostgreSQL, PGSTY Silo, Airflow, Grafana and
Prometheus data. They stop the Compose services before copying the volumes;
running jobs can be interrupted. A successful PostgreSQL shutdown is required.
Other running containers must not mount these volumes.

The result is a physical, offline backup, not simultaneous snapshots. It is
consistent only after all writers have stopped; PostgreSQL may need its normal
crash recovery for transactions interrupted by shutdown. Backups include
database credentials and other sensitive data: restrict access and store an
encrypted copy off-host. Bind mounts (including notebooks and application
source), Compose configuration, images, and external services are not backed
up. Preserve those separately. Use the same Compose configuration and
compatible service images when restoring physical data.

## Backup

Requires Docker Compose, the locally available `postgres:16-alpine` image,
`jq`, `gzip`, `tar`, `diff` and `sha256sum`. Only local Compose volumes
without driver options are supported.

```bash
./scripts/backup.sh
./scripts/test_backup_restore.sh /absolute/path/to/backup
```

By default, the previously running Compose services are restarted even if the
backup fails. To leave services stopped after a successful backup, use
`./scripts/backup.sh --leave-stopped`. A failed backup is incomplete and must
not be used. The output prints the backup path. The test checks archive
readability and checksums; it does not prove that the applications can read
the restored data. Perform a restore drill to establish that.

## Restore to fresh volumes

The restore script refuses to overwrite a non-empty or mounted volume. This
procedure **deletes the current Compose volumes**; first verify the backup and
retain an independent copy. Confirm that the backup is outside those volumes.

```bash
./scripts/test_backup_restore.sh /absolute/path/to/backup
docker compose down -v
./scripts/restore.sh /absolute/path/to/backup
docker compose up -d
```

Check service health, catalog tables and Silo objects after startup. If restore
fails, leave the services stopped; inspect the error and retain the backup.
The restore creates missing volumes and only accepts a backup whose volume
mapping matches the current Compose project. Reset partially restored volumes
before retrying; it never clears them automatically.
