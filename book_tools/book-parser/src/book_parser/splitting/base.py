"""Splitter contract and the shared slicing logic."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ..models import Chapter

CHAPTER = "chapter"
PART = "part"


@dataclass(frozen=True)
class Boundary:
    """A heading found in the document.

    ``start`` is the first line of the heading, ``body_start`` the first line
    of the text that belongs to it.
    """

    start: int
    body_start: int
    name: str
    kind: str = CHAPTER


class ChapterSplitter(Protocol):
    name: str

    def find_boundaries(self, lines: list[str]) -> list[Boundary] | None:
        """Return boundaries, or ``None`` when the strategy does not apply."""


def build_chapters(
    lines: list[str], boundaries: list[Boundary]
) -> list[Chapter]:
    """Cut ``lines`` at the boundaries; parts only label their chapters."""
    ordered = sorted(boundaries, key=lambda b: b.start)
    chapters: list[Chapter] = []
    part: str | None = None
    for i, boundary in enumerate(ordered):
        if boundary.kind == PART:
            part = boundary.name
            continue
        end = ordered[i + 1].start if i + 1 < len(ordered) else len(lines)
        text = "\n".join(
            lines[boundary.body_start : max(end, boundary.body_start)]
        )
        if not text.strip():
            continue
        chapters.append(
            Chapter(
                number=len(chapters) + 1,
                name=boundary.name,
                text=text.strip(),
                part=part,
            )
        )
    return chapters


def chapter_boundaries(boundaries: list[Boundary]) -> list[Boundary]:
    return [b for b in boundaries if b.kind == CHAPTER]
