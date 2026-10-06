"""Presentations: every slide is a chapter."""

from __future__ import annotations

import re

from ..text_utils import strip_markdown
from .base import Boundary

_SLIDE = re.compile(r"^\s*<!--\s*Slide number:\s*(\d+)\s*-->\s*$")
_HEADING = re.compile(r"^\s*#{1,6}\s+(.*\S)")


class SlideSplitter:
    name = "slides"

    def find_boundaries(self, lines: list[str]) -> list[Boundary] | None:
        starts = [i for i, line in enumerate(lines) if _SLIDE.match(line)]
        if len(starts) < 2:
            return None
        boundaries = []
        for i, start in enumerate(starts):
            end = starts[i + 1] if i + 1 < len(starts) else len(lines)
            number = _SLIDE.match(lines[start]).group(1)
            title = next(
                (
                    strip_markdown(m.group(1))
                    for line in lines[start + 1 : end]
                    if (m := _HEADING.match(line))
                ),
                "",
            )
            name = f"Slide {number}: {title}" if title else f"Slide {number}"
            boundaries.append(Boundary(start, start + 1, name))
        return boundaries
