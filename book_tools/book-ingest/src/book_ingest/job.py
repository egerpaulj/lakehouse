"""The ingest use case: inbox folder -> parsed items -> Delta table."""

from __future__ import annotations

import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Protocol


from .archive import FileArchiver
from .scanner import FolderScanner

logger = logging.getLogger("book_ingest")


class Item(Protocol):
    filename: str
    file_hash: str


class Parser(Protocol):
    def parse(self, path: Path) -> Item: ...


class Store(Protocol):
    def ensure_table(self) -> None: ...

    def known_hashes(self) -> set[str]: ...

    def add(self, item: Any) -> int: ...


@dataclass
class IngestResult:
    ingested: list[str] = field(default_factory=list)
    duplicates: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    rows: int = 0

    @property
    def total(self) -> int:
        return len(self.ingested) + len(self.duplicates) + len(self.failed)


class IngestJob:
    def __init__(
        self,
        scanner: FolderScanner,
        parser: Parser,
        store: Store,
        archiver: FileArchiver,
    ):
        self._scanner = scanner
        self._parser = parser
        self._store = store
        self._archiver = archiver

    def run(self) -> IngestResult:
        result = IngestResult()
        files = self._scanner.pending()
        if not files:
            logger.info("No documents to ingest")
            return result
        self._store.ensure_table()
        known = self._store.known_hashes()
        for path in files:
            try:
                item = self._parser.parse(path)
            except Exception as error:  # noqa: BLE001 - keep the batch going
                logger.exception("Failed to parse %s", path.name)
                result.failed.append(path.name)
                self._archiver.mark_failed(path, repr(error))
                continue
            # Store errors (Spark down...) propagate: the file stays in the
            # inbox and the next run retries it.
            if item.file_hash in known:
                result.duplicates.append(path.name)
                logger.info("%s already ingested, skipping", path.name)
            else:
                rows = self._store.add(item)
                result.rows += rows
                known.add(item.file_hash)
                result.ingested.append(path.name)
                logger.info("%s: %d rows written", path.name, rows)
            self._archiver.mark_processed(path)
        return result
