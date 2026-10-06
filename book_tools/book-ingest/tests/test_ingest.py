from pathlib import Path

from book_ingest import FileArchiver, FolderScanner, IngestJob
from book_ingest.repository import SCHEMA, book_rows
from book_parser.models import Book, Chapter


def make_book(path: Path, file_hash: str) -> Book:
    return Book(
        filename=path.name,
        file_hash=file_hash,
        title="T",
        author="A",
        publication_date=None,
        markdown="m",
        split_strategy="x",
        chapters=(Chapter(1, "One", "text", None),),
    )


class FakeParser:
    def parse(self, path):
        if "bad" in path.name:
            raise ValueError("boom")
        return make_book(path, path.read_text())


class FakeStore:
    def __init__(self, known=()):
        self.known = set(known)
        self.added = []
        self.ensured = False

    def ensure_table(self):
        self.ensured = True

    def known_hashes(self):
        return set(self.known)

    def add(self, book):
        self.added.append(book.filename)
        return len(book.chapters)


def job(folder, store):
    return IngestJob(
        FolderScanner(folder),
        FakeParser(),
        store,
        FileArchiver(folder),
    )


def test_empty_folder_does_nothing(tmp_path):
    store = FakeStore()
    result = job(tmp_path, store).run()
    assert result.total == 0
    assert not store.ensured


def test_scanner_ignores_unsupported_and_hidden(tmp_path):
    for name in ("a.epub", "b.xyz", ".c.pdf", "~$d.docx", "e.PDF"):
        (tmp_path / name).write_text("x")
    (tmp_path / "processed").mkdir()
    names = [p.name for p in FolderScanner(tmp_path).pending()]
    assert names == ["a.epub", "e.PDF"]


def test_ingest_dedupe_and_failures(tmp_path):
    (tmp_path / "new.epub").write_text("h1")
    (tmp_path / "dup.epub").write_text("h2")
    (tmp_path / "bad.epub").write_text("h3")
    store = FakeStore(known={"h2"})
    result = job(tmp_path, store).run()
    assert result.ingested == ["new.epub"]
    assert result.duplicates == ["dup.epub"]
    assert result.failed == ["bad.epub"]
    assert result.rows == 1
    assert store.added == ["new.epub"]
    assert (tmp_path / "processed" / "new.epub").exists()
    assert (tmp_path / "processed" / "dup.epub").exists()
    assert (tmp_path / "failed" / "bad.epub").exists()
    assert FolderScanner(tmp_path).pending() == []


def test_archiver_handles_name_collision(tmp_path):
    archiver = FileArchiver(tmp_path)
    for _ in range(2):
        f = tmp_path / "a.epub"
        f.write_text("x")
        archiver.mark_processed(f)
    assert len(list((tmp_path / "processed").iterdir())) == 2


def test_book_rows_match_schema(tmp_path):
    rows = book_rows(make_book(tmp_path / "a.epub", "h"))
    assert len(rows) == 1 and len(rows[0]) == len(SCHEMA.fields)


def test_document_parser_and_rows(tmp_path):
    from book_ingest.repository import DOCUMENT_SCHEMA, document_rows
    from book_parser import DocumentParser

    class Conv:
        def convert(self, path):
            return "**Title:** T\n\n**Authors:** A\n\nhello world"

    path = tmp_path / "note.txt"
    path.write_text("x")
    doc = DocumentParser(Conv()).parse(path)
    assert (doc.extension, doc.size_bytes, doc.text) == (
        "txt",
        1,
        "hello world",
    )
    assert doc.author == "A"
    rows = document_rows(doc)
    assert len(rows) == 1 and len(rows[0]) == len(DOCUMENT_SCHEMA.fields)
