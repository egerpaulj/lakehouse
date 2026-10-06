"""Ingest files from a folder into a Delta table via Spark Connect.

--scan-type book     split into chapters (one row per chapter)
--scan-type generic  one row per file (text plus inferred metadata)

Nothing happens (and Spark is never contacted) when the folder is empty.
Requires the book-parser and book-ingest packages (book_tools/).
"""

import argparse
import logging
import os
import sys

from book_ingest import (
    BooksRepository,
    DocumentsRepository,
    FileArchiver,
    FolderScanner,
    IngestJob,
)
from book_parser import BookParser, DocumentParser

SCAN_TYPES = {
    "book": ("books_b0", BookParser, BooksRepository),
    "generic": ("documents_b0", DocumentParser, DocumentsRepository),
}


def main(argv=None) -> int:
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument("--folder", required=True, help="folder to scan")
    args.add_argument(
        "--catalog", default="crawler", help="target catalog/database"
    )
    args.add_argument(
        "--table",
        help="target table (default: books_b0 for book, documents_b0 "
        "for generic)",
    )
    args.add_argument(
        "--scan-type", choices=sorted(SCAN_TYPES), default="book"
    )
    options = args.parse_args(argv)
    logging.basicConfig(level=logging.INFO)

    default_table, parser_cls, repository_cls = SCAN_TYPES[options.scan_type]
    table = f"{options.catalog}.{options.table or default_table}"

    scanner = FolderScanner(options.folder)
    if not scanner.pending():
        print(f"No documents in {options.folder}; nothing to do")
        return 0

    from pyspark.sql import SparkSession

    spark = (
        SparkSession.builder.remote(
            os.environ.get("SPARK_CONNECT_URL", "sc://spark-connect:15002")
        )
        .appName(f"ingest_{options.scan_type}")
        .getOrCreate()
    )
    try:
        result = IngestJob(
            scanner,
            parser_cls(),
            repository_cls(spark, table),
            FileArchiver(options.folder),
        ).run()
    finally:
        spark.stop()
    print(
        f"table={table} ingested={len(result.ingested)} rows={result.rows} "
        f"duplicates={len(result.duplicates)} failed={len(result.failed)}"
    )
    return 1 if result.failed else 0


if __name__ == "__main__":
    sys.exit(main())
