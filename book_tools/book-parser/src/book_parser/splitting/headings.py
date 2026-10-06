"""Documents that carry real Markdown headings (Word, many EPUBs)."""

from __future__ import annotations

import re

from ..text_utils import is_part_title, normalize, strip_markdown
from .base import PART, Boundary

_HEADING = re.compile(r"^\s{0,3}(#{1,6})\s+(.*\S)\s*$")
_IGNORED = {
    "contents",
    "table of contents",
    "cover",
    "title page",
    "copyright",
}
MIN_AVG_CHARS = 800


class HeadingSplitter:
    name = "headings"

    def find_boundaries(self, lines: list[str]) -> list[Boundary] | None:
        by_level: dict[int, list[tuple[int, str]]] = {}
        for i, line in enumerate(lines):
            match = _HEADING.match(line)
            if not match:
                continue
            text = strip_markdown(match.group(2))
            norm = normalize(text)
            if not norm or norm in _IGNORED:
                continue
            by_level.setdefault(len(match.group(1)), []).append((i, text))

        level = self._pick_level(by_level)
        if level is None:
            return None
        found = by_level[level]
        chapter_count = sum(
            1 for _, t in found if not is_part_title(normalize(t))
        )
        total_chars = sum(len(line) for line in lines)
        if chapter_count < 2 or total_chars / chapter_count < MIN_AVG_CHARS:
            return None
        return [
            Boundary(
                i,
                i + 1,
                text,
                PART if is_part_title(normalize(text)) else "chapter",
            )
            for i, text in found
        ]

    @staticmethod
    def _pick_level(by_level: dict[int, list]) -> int | None:
        """Shallowest level with several headings, else any with two."""
        for minimum in (3, 2):
            for level in sorted(by_level):
                if len(by_level[level]) >= minimum:
                    return level
        return None
