"""Domain objects returned by the parser."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass(frozen=True)
class Chapter:
    number: int
    name: str
    text: str
    part: str | None = None


@dataclass(frozen=True)
class Metadata:
    title: str | None = None
    author: str | None = None
    publication_date: date | None = None

    def merged_with(self, fallback: Metadata) -> Metadata:
        """Keep own values, fill the gaps from ``fallback``."""
        return Metadata(
            title=self.title or fallback.title,
            author=self.author or fallback.author,
            publication_date=(
                self.publication_date or fallback.publication_date
            ),
        )


@dataclass(frozen=True)
class Book:
    filename: str
    file_hash: str
    title: str | None
    author: str | None
    publication_date: date | None
    markdown: str
    split_strategy: str
    chapters: list[Chapter] = field(default_factory=list)


@dataclass(frozen=True)
class Document:
    """A whole file converted to text, without chapter structure."""

    filename: str
    file_hash: str
    title: str | None
    author: str | None
    publication_date: date | None
    extension: str
    size_bytes: int
    modified_at: datetime
    text: str
