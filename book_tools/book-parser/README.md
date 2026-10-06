# book-parser

Spark-free library: file in, `Book` (with `Chapter`s) or `Document` out.
Conversion uses [markitdown](https://github.com/microsoft/markitdown).

```python
from book_parser import BookParser, DocumentParser

book = BookParser().parse("book.epub")
print(book.title, book.author, book.publication_date, book.split_strategy)
for c in book.chapters:
    print(c.number, c.part, c.name, len(c.text))

doc = DocumentParser().parse("notes.docx")  # whole text + metadata
```

Chapter splitting tries, in order: slides, table of contents, explicit
"Chapter N" markers, link headings, Markdown headings; otherwise the whole
text is one chapter.

```
pip install -e ".[dev]" && pytest
python -m build && twine upload dist/*
```
