"""Try the splitters from most to least specific."""

from __future__ import annotations

from ..models import Chapter
from .backlinks import BacklinkHeadingSplitter
from .base import ChapterSplitter, build_chapters
from .headings import HeadingSplitter
from .markers import ChapterMarkerSplitter
from .slides import SlideSplitter
from .toc import TableOfContentsSplitter

WHOLE_DOCUMENT = "whole_document"


def default_splitters() -> list[ChapterSplitter]:
    return [
        SlideSplitter(),
        TableOfContentsSplitter(),
        ChapterMarkerSplitter(),
        BacklinkHeadingSplitter(),
        HeadingSplitter(),
    ]


class ChapterSplitPipeline:
    def __init__(self, splitters: list[ChapterSplitter] | None = None):
        self._splitters = (
            splitters if splitters is not None else default_splitters()
        )

    def split(self, markdown: str) -> tuple[str, list[Chapter]]:
        """Return ``(strategy name, chapters)``."""
        lines = markdown.splitlines()
        for splitter in self._splitters:
            boundaries = splitter.find_boundaries(lines)
            if not boundaries:
                continue
            chapters = build_chapters(lines, boundaries)
            if len(chapters) >= 2:
                return splitter.name, chapters
        text = markdown.strip()
        return WHOLE_DOCUMENT, [Chapter(1, "Full text", text)]
