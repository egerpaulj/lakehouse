"""Move handled files out of the inbox so they are not read twice."""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path


class FileArchiver:
    def __init__(
        self,
        folder: str | Path,
        processed: str = "processed",
        failed: str = "failed",
    ):
        self._processed = Path(folder) / processed
        self._failed = Path(folder) / failed

    def mark_processed(self, path: Path) -> Path:
        return self._move(path, self._processed)

    def mark_failed(self, path: Path, reason: str) -> Path:
        target = self._move(path, self._failed)
        target.with_name(target.name + ".error.txt").write_text(reason)
        return target

    @staticmethod
    def _move(path: Path, folder: Path) -> Path:
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / path.name
        if target.exists():
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
            target = folder / f"{path.stem}.{stamp}{path.suffix}"
        shutil.move(str(path), str(target))
        return target
