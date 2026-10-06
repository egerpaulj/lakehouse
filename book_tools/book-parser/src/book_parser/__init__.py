"""Convert documents to Markdown and split them into chapters.

The library is independent of Spark: ``BookParser().parse(path)`` returns a
:class:`Book` made of :class:`Chapter` objects.
"""

from .models import Book, Chapter, Document
from .parser import BookParser, DocumentParser, default_parser

__all__ = [
    "Book",
    "BookParser",
    "Document",
    "DocumentParser",
    "Chapter",
    "default_parser",
]
