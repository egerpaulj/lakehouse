"""Persistence of parsed books in the Delta table."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from pyspark.sql import SparkSession
from pyspark.sql.types import (
    DateType,
    IntegerType,
    LongType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

from book_parser import Book, Document

DEFAULT_TABLE = "crawler.books_b0"
DEFAULT_DOCUMENTS_TABLE = "crawler.documents_b0"

SCHEMA = StructType(
    [
        StructField("chapter_id", StringType(), False),
        StructField("file_hash", StringType(), False),
        StructField("filename", StringType(), False),
        StructField("title", StringType(), True),
        StructField("author", StringType(), True),
        StructField("publication_date", DateType(), True),
        StructField("part_name", StringType(), True),
        StructField("chapter_number", IntegerType(), False),
        StructField("chapter_name", StringType(), True),
        StructField("text", StringType(), True),
        StructField("split_strategy", StringType(), True),
        StructField("ingested_at", TimestampType(), False),
    ]
)


DOCUMENT_SCHEMA = StructType(
    [
        StructField("document_id", StringType(), False),
        StructField("file_hash", StringType(), False),
        StructField("filename", StringType(), False),
        StructField("extension", StringType(), True),
        StructField("title", StringType(), True),
        StructField("author", StringType(), True),
        StructField("publication_date", DateType(), True),
        StructField("size_bytes", LongType(), True),
        StructField("modified_at", TimestampType(), True),
        StructField("char_count", IntegerType(), True),
        StructField("text", StringType(), True),
        StructField("ingested_at", TimestampType(), False),
    ]
)


def document_rows(
    document: Document, ingested_at: datetime | None = None
) -> list[tuple]:
    """A single row, in the order of :data:`DOCUMENT_SCHEMA`."""
    ingested_at = ingested_at or datetime.now(timezone.utc)
    return [
        (
            document.file_hash,
            document.file_hash,
            document.filename,
            document.extension,
            document.title,
            document.author,
            document.publication_date,
            document.size_bytes,
            document.modified_at,
            len(document.text),
            document.text,
            ingested_at,
        )
    ]


def book_rows(book: Book, ingested_at: datetime | None = None) -> list[tuple]:
    """One row per chapter, in the order of :data:`SCHEMA`."""
    ingested_at = ingested_at or datetime.now(timezone.utc)
    return [
        (
            hashlib.sha1(f"{book.file_hash}:{c.number}".encode()).hexdigest(),
            book.file_hash,
            book.filename,
            book.title,
            book.author,
            book.publication_date,
            c.part,
            c.number,
            c.name,
            c.text,
            book.split_strategy,
            ingested_at,
        )
        for c in book.chapters
    ]


class DeltaRepository:
    """Append-only Delta table keyed by ``file_hash``."""

    schema: StructType

    def __init__(self, spark: SparkSession, table: str):
        self._spark = spark
        self._table = table

    def _rows(self, item) -> list[tuple]:
        raise NotImplementedError

    def ensure_table(self) -> None:
        if "." in self._table:
            database = self._table.rsplit(".", 1)[0]
            self._spark.sql(
                f"CREATE DATABASE IF NOT EXISTS {database} "
                f"LOCATION 's3a://warehouse/{database.split('.')[-1]}'"
            )
        columns = ", ".join(
            f"{f.name} {f.dataType.simpleString().upper()}"
            f"{'' if f.nullable else ' NOT NULL'}"
            for f in self.schema.fields
        )
        self._spark.sql(
            f"CREATE TABLE IF NOT EXISTS {self._table} ({columns}) "
            "USING DELTA "
            "TBLPROPERTIES (delta.enableChangeDataFeed = true)"
        )

    def known_hashes(self) -> set[str]:
        rows = self._spark.table(self._table).select("file_hash").distinct()
        return {row.file_hash for row in rows.collect()}

    def add(self, item) -> int:
        """Append the rows of one file in a single commit; returns count."""
        rows = self._rows(item)
        if rows:
            (
                self._spark.createDataFrame(rows, self.schema)
                .write.format("delta")
                .mode("append")
                .saveAsTable(self._table)
            )
        return len(rows)


class BooksRepository(DeltaRepository):
    schema = SCHEMA

    def __init__(self, spark: SparkSession, table: str = DEFAULT_TABLE):
        super().__init__(spark, table)

    def _rows(self, book: Book) -> list[tuple]:
        return book_rows(book)


class DocumentsRepository(DeltaRepository):
    schema = DOCUMENT_SCHEMA

    def __init__(
        self, spark: SparkSession, table: str = DEFAULT_DOCUMENTS_TABLE
    ):
        super().__init__(spark, table)

    def _rows(self, document: Document) -> list[tuple]:
        return document_rows(document)
