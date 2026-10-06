"""Ingest a folder of documents into the Delta tables."""

from .archive import FileArchiver
from .job import IngestJob, IngestResult
from .repository import (
    DEFAULT_DOCUMENTS_TABLE,
    DEFAULT_TABLE,
    BooksRepository,
    DocumentsRepository,
)
from .scanner import FolderScanner

__all__ = [
    "DEFAULT_DOCUMENTS_TABLE",
    "DEFAULT_TABLE",
    "BooksRepository",
    "DocumentsRepository",
    "FileArchiver",
    "FolderScanner",
    "IngestJob",
    "IngestResult",
]
