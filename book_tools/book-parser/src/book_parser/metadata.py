"""Author, title and publication date from the best available source."""

from __future__ import annotations

import re
import zipfile
from datetime import date
from pathlib import Path
from typing import Protocol
from xml.etree import ElementTree

from .models import Metadata

_HEADER = re.compile(
    r"^\*\*(Title|Authors?|Language|Publisher|Date|Description|Identifier):"
    r"\*\*\s*(.*)$"
)


class MetadataExtractor(Protocol):
    def extract(self, path: Path, markdown: str) -> Metadata: ...


def parse_date(value: str | None) -> date | None:
    """Parse ISO dates, PDF ``D:2011...`` dates and bare years."""
    if not value:
        return None
    value = value.strip()
    if value.startswith("D:"):
        value = value[2:]
    match = re.match(r"(\d{4})-?(\d{2})?-?(\d{2})?", value)
    if not match:
        return None
    year, month, day = match.groups()
    try:
        return date(int(year), int(month or 1), int(day or 1))
    except ValueError:
        try:
            return date(int(year), int(month or 1), 1)
        except ValueError:
            return date(int(year), 1, 1)


def strip_metadata_header(markdown: str) -> tuple[dict[str, str], str]:
    """Split the ``**Title:** ...`` block markitdown puts on EPUBs."""
    lines = markdown.splitlines()
    fields: dict[str, str] = {}
    i = 0
    while i < len(lines):
        if not lines[i].strip():
            i += 1
            continue
        match = _HEADER.match(lines[i])
        if not match:
            break
        fields[match.group(1).lower().rstrip("s")] = match.group(2).strip()
        i += 1
    if not fields:
        return {}, markdown
    return fields, "\n".join(lines[i:])


class MarkdownHeaderMetadata:
    def extract(self, path: Path, markdown: str) -> Metadata:
        fields, _ = strip_metadata_header(markdown)
        return Metadata(
            title=fields.get("title") or None,
            author=fields.get("author") or None,
            publication_date=parse_date(fields.get("date")),
        )


class OoxmlMetadata:
    """Core properties of .docx / .pptx files."""

    _NS = {
        "dc": "http://purl.org/dc/elements/1.1/",
        "dcterms": "http://purl.org/dc/terms/",
    }

    def extract(self, path: Path, markdown: str) -> Metadata:
        if path.suffix.lower() not in (".docx", ".pptx"):
            return Metadata()
        try:
            with zipfile.ZipFile(path) as archive:
                root = ElementTree.fromstring(
                    archive.read("docProps/core.xml")
                )
        except (OSError, KeyError, zipfile.BadZipFile, ElementTree.ParseError):
            return Metadata()

        def text(tag: str) -> str | None:
            node = root.find(tag, self._NS)
            return (
                (node.text or "").strip() or None if node is not None else None
            )

        return Metadata(
            title=text("dc:title"),
            author=text("dc:creator"),
            publication_date=parse_date(text("dcterms:created")),
        )


class PdfInfoMetadata:
    def extract(self, path: Path, markdown: str) -> Metadata:
        if path.suffix.lower() != ".pdf":
            return Metadata()
        try:
            from pdfminer.pdfdocument import PDFDocument
            from pdfminer.pdfparser import PDFParser

            with open(path, "rb") as handle:
                info = PDFDocument(PDFParser(handle)).info[0]
        except Exception:  # noqa: BLE001 - metadata is best effort
            return Metadata()

        def text(key: str) -> str | None:
            value = info.get(key)
            if isinstance(value, bytes):
                value = value.decode("utf-8", "ignore")
            return str(value).strip() or None if value else None

        return Metadata(
            title=text("Title"),
            author=text("Author"),
            publication_date=parse_date(text("CreationDate")),
        )


class FilenameMetadata:
    """``Title (2011) - Noam Chomsky.pdf`` and ``Title by Noam Chomsky``."""

    _YEAR = re.compile(r"\((\d{4})(?:\s*,\s*\d{4})*\)")
    _AUTHOR = re.compile(
        r"(?:\s-\s|\sby\s)((?:[A-Z][\w.'’]*\s?){2,4}(?:\s&\s(?:[A-Z][\w.'’]*\s?){2,4})?)$"
    )

    def extract(self, path: Path, markdown: str) -> Metadata:
        stem = path.stem
        year = self._YEAR.search(stem)
        stem_no_year = self._YEAR.sub("", stem).strip(" -_")
        author = self._AUTHOR.search(stem_no_year)
        title = stem_no_year[: author.start()] if author else stem_no_year
        return Metadata(
            title=title.strip(" -_") or None,
            author=author.group(1).strip() if author else None,
            publication_date=(
                date(int(year.group(1)), 1, 1) if year else None
            ),
        )


class ChainedMetadata:
    """First extractor with a value wins, per field."""

    def __init__(self, extractors: list[MetadataExtractor]):
        self._extractors = extractors

    def extract(self, path: Path, markdown: str) -> Metadata:
        result = Metadata()
        for extractor in self._extractors:
            result = result.merged_with(extractor.extract(path, markdown))
        return result


def default_metadata_extractor() -> ChainedMetadata:
    return ChainedMetadata(
        [
            MarkdownHeaderMetadata(),
            OoxmlMetadata(),
            PdfInfoMetadata(),
            FilenameMetadata(),
        ]
    )


__all__ = [
    "ChainedMetadata",
    "FilenameMetadata",
    "MarkdownHeaderMetadata",
    "MetadataExtractor",
    "OoxmlMetadata",
    "PdfInfoMetadata",
    "default_metadata_extractor",
    "parse_date",
    "strip_metadata_header",
]
