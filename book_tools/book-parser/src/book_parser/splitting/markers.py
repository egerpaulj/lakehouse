"""Chapters announced in the text itself (``Chapter 1``, ``Part II`` ...)."""

from __future__ import annotations

import re

from ..text_utils import (
    is_number_marker,
    normalize,
    parse_number,
    strip_markdown,
)
from .base import CHAPTER, PART, Boundary

MAX_MARKER_LINE = 100
MAX_TITLE_LINE = 150
DENSE_LINES = 6

_MARKER = re.compile(
    r"^(?P<kind>chapter|chap\.?|part|book)\s+"
    r"(?P<num>\d{1,3}|[ivx]{1,5}|[a-z]+(?:[- ][a-z]+)?)"
    r"(?P<rest>\s*[:.\-–—]?\s*.*)$",
    re.IGNORECASE,
)
FRONT = {"preface", "foreword", "introduction", "prologue"}
BACK = {"epilogue", "afterword", "conclusion", "appendix", "notes"}


class ChapterMarkerSplitter:
    name = "chapter_markers"

    def find_boundaries(self, lines: list[str]) -> list[Boundary] | None:
        numbered, parts = self._scan(lines)
        chain = _longest_chain(_drop_dense(numbered))
        if len(chain) < 3:
            return None
        boundaries = list(chain)
        first, last = chain[0].start, chain[-1].start
        boundaries += [p for p in parts if p.start < last]
        boundaries += self._special_sections(lines, first, last)
        return sorted(boundaries, key=lambda b: b.start)

    def _scan(self, lines):
        numbered: list[tuple[int, Boundary]] = []
        parts: list[Boundary] = []
        i = 0
        while i < len(lines):
            text = strip_markdown(lines[i])
            if not text or len(text) > MAX_MARKER_LINE:
                i += 1
                continue
            match = _MARKER.match(text)
            parsed = None
            if match:
                tokens = normalize(match.group("num")).split()
                parsed = parse_number(tokens)
            if not match or parsed is None or parsed[1] != len(tokens):
                i += 1
                continue
            kind = match.group("kind").lower()
            rest = match.group("rest").strip(" :.-–—")
            if rest and (rest[0] in ",;)" or rest[0].islower()):
                i += 1  # prose such as "Chapter 4: , is ..."
                continue
            title_end = i
            if not rest:
                nxt = _next_text_line(lines, i)
                if nxt is not None:
                    rest, title_end = strip_markdown(lines[nxt]), nxt
            label = f"{text[: match.end('num')]}"
            name = f"{label}: {rest}" if rest else label
            body_start = title_end + 1
            if kind.startswith("chap"):
                numbered.append(
                    (parsed[0], Boundary(i, body_start, name, CHAPTER))
                )
            else:
                parts.append(Boundary(i, body_start, name, PART))
            i = body_start
        return numbered, parts

    def _special_sections(self, lines, first, last):
        found, seen = [], set()
        for i, line in enumerate(lines):
            text = strip_markdown(line)
            norm = normalize(text)
            if len(text) > 40 or norm in seen:
                continue
            if (norm in FRONT and i < first) or (norm in BACK and i > last):
                seen.add(norm)
                found.append(Boundary(i, i + 1, text, CHAPTER))
        return found


def _next_text_line(lines: list[str], index: int) -> int | None:
    """Next non-blank line within a short distance, if it looks like a title."""
    for j in range(index + 1, min(index + 4, len(lines))):
        text = strip_markdown(lines[j])
        if not text:
            continue
        if len(text) > MAX_TITLE_LINE or is_number_marker(normalize(text)):
            return None
        return j
    return None


def _drop_dense(
    numbered: list[tuple[int, Boundary]],
) -> list[tuple[int, Boundary]]:
    """Remove markers that sit in a table of contents (a few lines apart)."""

    def close(a, b):
        return a[0] != b[0] and abs(a[1].start - b[1].start) <= DENSE_LINES

    return [
        item
        for k, item in enumerate(numbered)
        if not (k > 0 and close(item, numbered[k - 1]))
        and not (k + 1 < len(numbered) and close(item, numbered[k + 1]))
    ]


def _longest_chain(
    numbered: list[tuple[int, Boundary]],
) -> list[Boundary]:
    """Longest ``n, n+1, n+2...`` run; repeated running headers are skipped."""
    best: list[Boundary] = []
    for s in range(len(numbered)):
        chain = [numbered[s][1]]
        expected = numbered[s][0] + 1
        for number, boundary in numbered[s + 1 :]:
            if number == expected:
                chain.append(boundary)
                expected += 1
        if len(chain) > len(best):
            best = chain
    return best
