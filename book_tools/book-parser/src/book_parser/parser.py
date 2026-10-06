"""Facade: file in, :class:`Book` out."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from .converters import DocumentConverter, MarkItDownConverter
from .metadata import (
    MetadataExtractor,
    default_metadata_extractor,
    strip_metadata_header,
)
from .models import Book, Document
from .splitting import ChapterSplitPipeline


class BookParser:
    def __init__(
        self,
        converter: DocumentConverter | None = None,
        metadata: MetadataExtractor | None = None,
        splitter: ChapterSplitPipeline | None = None,
    ):
        self._converter = converter or MarkItDownConverter()
        self._metadata = metadata or default_metadata_extractor()
        self._splitter = splitter or ChapterSplitPipeline()

    def parse(self, path: str | Path) -> Book:
        path = Path(path)
        raw = self._converter.convert(path)
        metadata = self._metadata.extract(path, raw)
        _, markdown = strip_metadata_header(raw)
        strategy, chapters = self._splitter.split(markdown)
        return Book(
            filename=path.name,
            file_hash=file_sha256(path),
            title=metadata.title,
            author=metadata.author,
            publication_date=metadata.publication_date,
            markdown=markdown,
            split_strategy=strategy,
            chapters=chapters,
        )


class DocumentParser:
    """File in, :class:`Document` (full text plus metadata) out."""

    def __init__(
        self,
        converter: DocumentConverter | None = None,
        metadata: MetadataExtractor | None = None,
    ):
        self._converter = converter or MarkItDownConverter()
        self._metadata = metadata or default_metadata_extractor()

    def parse(self, path: str | Path) -> Document:
        path = Path(path)
        raw = self._converter.convert(path)
        metadata = self._metadata.extract(path, raw)
        _, text = strip_metadata_header(raw)
        stat = path.stat()
        return Document(
            filename=path.name,
            file_hash=file_sha256(path),
            title=metadata.title,
            author=metadata.author,
            publication_date=metadata.publication_date,
            extension=path.suffix.lower().lstrip("."),
            size_bytes=stat.st_size,
            modified_at=datetime.fromtimestamp(stat.st_mtime, timezone.utc),
            text=text,
        )


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def default_parser() -> BookParser:
    return BookParser()
