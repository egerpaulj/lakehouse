from book_parser.models import Book
from book_parser.parser import BookParser
from book_parser.splitting.pipeline import ChapterSplitPipeline

BODY = "\n\n".join(["Lorem ipsum dolor sit amet. " * 10] * 8)


class FakeConverter:
    def __init__(self, markdown):
        self.markdown = markdown

    def convert(self, path):
        return self.markdown


class NoMetadata:
    def extract(self, path, markdown):
        from book_parser.models import Metadata

        return Metadata()


def split(markdown):
    return ChapterSplitPipeline().split(markdown)


def test_table_of_contents_with_links():
    md = (
        "Contents\n\n> [Introduction](a.html#1)\n\n"
        "> [One Old Wine](a.html#2)\n\n> [Two New Bottles](a.html#3)\n\n"
        f"Introduction\n\n{BODY}\n\nOne Old Wine\n\n{BODY}\n\n"
        f"Two New Bottles\n\n{BODY}\n"
    )
    strategy, chapters = split(md)
    assert strategy == "table_of_contents"
    assert [c.name for c in chapters] == [
        "Introduction",
        "One Old Wine",
        "Two New Bottles",
    ]
    assert all(BODY.strip() in c.text for c in chapters)


def test_toc_matches_word_numbers_to_digits():
    md = (
        "Contents\n\n[1. Alpha](a.html#1)\n\n[2. Beta](a.html#2)\n\n"
        f"ONE Alpha\n\n{BODY}\n\nTWO Beta\n\n{BODY}\n"
    )
    _, chapters = split(md)
    assert len(chapters) == 2


def test_explicit_chapter_markers_with_parts():
    md = (
        f"Part I\n\nOld Wine, New Bottles\n\nChapter 1\n\nBeginnings\n\n{BODY}\n\n"
        f"Chapter 2\n\nMiddles\n\n{BODY}\n\nChapter 3\n\nEndings\n\n{BODY}\n"
    )
    strategy, chapters = split(md)
    assert strategy == "chapter_markers"
    assert len(chapters) == 3
    assert chapters[0].part and "Part I" in chapters[0].part
    assert "Beginnings" in chapters[0].name


def test_prose_mentioning_chapter_is_not_a_marker():
    md = (
        "Chapter 4: , is a study\n\n"
        + BODY
        + "\n\nChapter 5: is more\n\n"
        + BODY
    )
    strategy, chapters = split(md)
    assert strategy == "whole_document"
    assert len(chapters) == 1


def test_markdown_headings():
    md = "".join(f"# Chapter title {n}\n\n{BODY * 4}\n\n" for n in "ABCD")
    strategy, chapters = split(md)
    assert strategy == "headings"
    assert len(chapters) == 4


def test_slides():
    md = "".join(
        f"<!-- Slide number: {i} -->\n# Slide {i}\n\ntext {i}\n\n"
        for i in (1, 2, 3)
    )
    strategy, chapters = split(md)
    assert strategy == "slides"
    assert len(chapters) == 3


def test_fallback_whole_document():
    strategy, chapters = split("just some text without structure")
    assert strategy == "whole_document"
    assert len(chapters) == 1


def test_parser_builds_book(tmp_path):
    path = tmp_path / "Some Book (2011) - Jane Doe.epub"
    path.write_bytes(b"x")
    md = (
        "**Title:** Some Book\n\n**Authors:** Jane Doe\n\n"
        "**Date:** 2011-05-06\n\n"
        + "Chapter 1\n\nA\n\n"
        + BODY
        + "\n\nChapter 2\n\nB\n\n"
        + BODY
        + "\n\nChapter 3\n\nC\n\n"
        + BODY
    )
    book = BookParser(FakeConverter(md), NoMetadata()).parse(path)
    assert isinstance(book, Book)
    assert book.filename == path.name
    assert len(book.chapters) == 3
    assert [c.number for c in book.chapters] == [1, 2, 3]
