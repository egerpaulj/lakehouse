# book-ingest

Reads a folder with `book-parser` and appends to Delta tables through Spark
Connect (`BooksRepository` -> one row per chapter, `DocumentsRepository` ->
one row per file). Processed files move to `processed/`, unreadable ones to
`failed/`; files already in the table (same hash) are skipped.

```python
IngestJob(FolderScanner(d), BookParser(), BooksRepository(spark), FileArchiver(d)).run()
```

Spark job: `spark-apps/ingest_files.py --folder ... --catalog crawler
--table books_b0 --scan-type book|generic`.

```
pip install -e ../book-parser -e ".[dev]" && pytest
python -m build && twine upload dist/*   # publish book-parser first
```

## Dropping books/files into the inbox

The hourly `books_ingest_hourly` DAG runs two independent tasks:

- `ingest_books` scans `/opt/airflow/data/books/inbox` (`--scan-type book`)
  and appends one row per chapter to `crawler.books_b0`.
- `ingest_files` scans `/opt/airflow/data/files/inbox` (`--scan-type
  generic`) and appends one row per file to `crawler.documents_b0`.

Both paths live inside the `airflow` container and are backed by the
`airflow-data` named Docker volume (not a host bind mount), so files must be
copied in rather than placed directly on the host filesystem.

Find the volume's location on the host:

```
docker volume inspect lakehouse_airflow-data --format '{{ .Mountpoint }}'
```

Copy a book or a generic file into the relevant inbox using
`docker compose cp` (run from the repo root, where `docker-compose.yml`
lives):

```
docker compose cp ./my-book.epub airflow:/opt/airflow/data/books/inbox/
docker compose cp ./my-file.pdf airflow:/opt/airflow/data/files/inbox/
```

The next run of `books_ingest_hourly` (or a manual trigger from the Airflow
UI at http://localhost:8088) will pick up any new files.

### Permission denied moving to `processed/`/`failed/`

`docker cp`/`docker compose cp` runs as root and will create any missing
parent directories (e.g. `books/inbox` or `files/inbox`) as root. The Airflow
tasks run as the `airflow` user, so `FileArchiver` then fails with
`PermissionError` when it tries to `mkdir` the `processed`/`failed` folders
it creates *inside* the inbox folder (e.g. `books/inbox/processed`). The
[Dockerfile](/home/user/src/lakehouse/airflow/Dockerfile) pre-creates these
folders owned by `airflow`, but on a volume created before
that was added (or if paths were created another way), fix it with:

```
docker compose exec -u root airflow chown -R airflow /opt/airflow/data
```

## Supported file extensions

`FolderScanner` only picks up files whose extension is in
`book_parser.converters.SUPPORTED_EXTENSIONS` (anything else is ignored).
Images and audio need optional system tools (`exiftool`, `ffmpeg`) or an LLM;
without them, conversion fails and the file is moved to `failed/`.

| Category          | Extensions |
|-------------------|------------|
| Documents         | `.pdf`, `.epub`, `.docx`, `.pptx`, `.xlsx`, `.xls`, `.msg` |
| Web/markup        | `.html`, `.htm`, `.xml`, `.rss`, `.atom`, `.md`, `.markdown` |
| Data              | `.csv`, `.json`, `.jsonl` |
| Plain text        | `.txt`, `.text` |
| Notebooks         | `.ipynb` |
| Archives          | `.zip` |
| Images            | `.jpg`, `.jpeg`, `.png` |
| Audio/video       | `.wav`, `.mp3`, `.m4a`, `.mp4` |
