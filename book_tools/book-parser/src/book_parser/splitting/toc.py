"""Split with the book's own table of contents.

The table of contents is parsed (linked EPUB style or plain text lines) and
every entry is then located, in order, in the text that follows it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..text_utils import (
    canonical,
    is_number_marker,
    is_part_title,
    normalize,
    strip_markdown,
    strip_number_prefix,
)
from .base import CHAPTER, PART, Boundary

MIN_MATCH_RATIO = 0.6
MIN_PREFIX_CHARS = 25
PREFIX_SLACK = 25
MAX_WINDOW = 3
MAX_HEADING_LINE = 200
LOOKAHEAD_FULL_FORM = 6
SEARCH_FRACTION = 0.3
MIN_HEADLESS_ENTRIES = 3

_TOC_HEADING = re.compile(
    r"^\s*(?:#{1,6}\s*)?[*_\s]*(?:table of contents|contents)[*_\s]*$",
    re.IGNORECASE,
)
_LINK_ONLY = re.compile(r"^\s*(?:[>*+\-]\s+)*\[[^\]!][^\]]*\]\([^)]*\)\s*$")
_LINK = re.compile(r"\[([^\]]*)\]\(([^)]*)\)")
_BULLET = re.compile(r"^(\s*)(?:[>*+\-]\s+|\d+[.)]\s+)*")
_LEADER = re.compile(r"(?:\s*\.{2,}\s*|\t+|\s{3,})(?:[0-9]+|[ivxlc]+)\s*$")
_TRAILING_PAGE = re.compile(r"\s+\.{2,}\s*$")
_SKIPPED_TITLES = {
    "cover",
    "title page",
    "half title",
    "copyright",
    "copyright page",
    "contents",
    "table of contents",
    "also by",
    "books by",
    "series page",
}


@dataclass
class TocEntry:
    title: str
    depth: int = 0
    is_part: bool = False
    forms: list[str] = field(default_factory=list)

    def __post_init__(self):
        self.is_part = is_part_title(normalize(self.title))
        self.forms = _match_forms(self.title)


def _match_forms(title: str) -> list[str]:
    """Normalised spellings of a title, most specific first."""
    full = canonical(normalize(title))
    stripped, _ = strip_number_prefix(full)
    forms = [full]
    if stripped and stripped != full:
        forms.append(stripped)
    return forms


class TableOfContentsSplitter:
    name = "table_of_contents"

    def find_boundaries(self, lines: list[str]) -> list[Boundary] | None:
        for heading, entries, end in self._candidates(lines):
            entries = _select_chapter_level(entries)
            boundaries = _locate(lines, entries, end)
            if boundaries is not None:
                return boundaries
        return None

    def _candidates(self, lines):
        limit = max(400, int(len(lines) * SEARCH_FRACTION))
        for i, line in enumerate(lines[:limit]):
            if not _TOC_HEADING.match(line):
                continue
            entries, end = _parse_entries(lines, i + 1)
            if len(entries) >= 2:
                yield i, entries, end
        yield from self._headless_candidates(lines, limit)

    def _headless_candidates(self, lines, limit):
        """A run of link-only lines near the start, without a heading."""
        i = 0
        while i < min(limit, len(lines)):
            if not _LINK_ONLY.match(lines[i]):
                i += 1
                continue
            entries, end = _parse_linked(lines, i)
            if len(entries) >= MIN_HEADLESS_ENTRIES:
                yield i, entries, end
            i = max(end, i + 1)


# --------------------------------------------------------------- parsing


def _parse_entries(lines: list[str], start: int):
    first = next((ln for ln in lines[start : start + 12] if ln.strip()), "")
    if _LINK.search(first):
        return _parse_linked(lines, start)
    return _parse_plain(lines, start)


def _parse_linked(lines: list[str], start: int):
    """Entries from Markdown links; consecutive links to one target merge."""
    raw: list[tuple[int, str, str]] = []  # depth, text, href
    end = start
    i = start - 1
    while i + 1 < len(lines):
        i += 1
        line = lines[i]
        while line.count("[") > line.count("]") and i + 1 < len(lines):
            i += 1  # link text wrapped over several lines
            line += " " + lines[i].strip()
        if not line.strip() or re.fullmatch(r"[\s|:\-]+", line):
            continue
        links = _LINK.findall(line)
        if not links:
            break
        depth = len(_BULLET.match(line.replace("\t", "  ")).group(1)) // 2
        for text, href in links:
            text = strip_markdown(text)
            if text:
                raw.append((depth, text, href))
        end = i + 1
    return _merge_same_target(raw), end


def _merge_same_target(raw: list[tuple[int, str, str]]) -> list[TocEntry]:
    groups: list[tuple[int, list[str], str]] = []
    for depth, text, href in raw:
        if (
            groups
            and groups[-1][2] == href
            and groups[-1][0] == depth
            and not _starts_new_entry(groups[-1][1], text)
        ):
            groups[-1][1].append(text)
        else:
            groups.append((depth, [text], href))
    entries = []
    for depth, texts, _ in groups:
        entries.append(TocEntry(join_title(texts), depth))
    return entries


def _starts_new_entry(previous: list[str], text: str) -> bool:
    """A numbered title after a titled one is a new entry (part + chapter 1)."""
    if all(is_number_marker(normalize(p)) for p in previous):
        return False
    return strip_number_prefix(normalize(text))[1] is not None


def join_title(texts: list[str]) -> str:
    """``["I", "Neoliberalism"]`` -> ``"I. Neoliberalism"``."""
    if len(texts) > 1 and is_number_marker(normalize(texts[0])):
        return f"{texts[0]}. {' '.join(texts[1:])}"
    return " ".join(texts)


def _parse_plain(lines: list[str], start: int):
    """Entries from plain lines (PDF); stops at the first body-like line."""
    titles: list[str] = []
    end = start
    first_norm = None
    for i in range(start, min(len(lines), start + 400)):
        text = strip_markdown(lines[i])
        if not text:
            continue
        if len(text) > 110 or (text.endswith(".") and len(text.split()) > 8):
            break
        norm = normalize(text)
        if first_norm is None and norm:
            first_norm = norm
        elif norm == first_norm and len(titles) >= 2:
            break
        cleaned = _LEADER.sub("", _TRAILING_PAGE.sub("", text)).strip()
        if titles and cleaned[:1].islower():
            titles[-1] += " " + cleaned
        elif cleaned:
            titles.append(cleaned)
        end = i + 1
    return [TocEntry(t) for t in titles], end


def _select_chapter_level(entries: list[TocEntry]) -> list[TocEntry]:
    """Keep chapter level entries (and parts); drop nested sub-sections."""
    kept: list[TocEntry] = []
    part_depths: list[int] = []
    levels: list[int] = []
    for entry in entries:
        while part_depths and part_depths[-1] >= entry.depth:
            part_depths.pop()
        levels.append(entry.depth - len(part_depths))
        if entry.is_part:
            part_depths.append(entry.depth)
    chapter_levels = [lv for e, lv in zip(entries, levels) if not e.is_part]
    if not chapter_levels:
        return []
    target = min(chapter_levels)
    for entry, level in zip(entries, levels):
        if normalize(entry.title) in _SKIPPED_TITLES:
            continue
        if entry.is_part or level == target:
            kept.append(entry)
    return kept


# -------------------------------------------------------------- locating


class _BodyIndex:
    """Normalised view of the non-blank, heading sized lines."""

    def __init__(self, lines: list[str], start: int):
        self.lines = lines
        self.idx: list[int] = []
        self.norm: list[str] = []
        for i in range(start, len(lines)):
            text = strip_markdown(lines[i])
            if text and len(text) <= MAX_HEADING_LINE:
                self.idx.append(i)
                self.norm.append(canonical(normalize(text)))
            elif text:
                self.idx.append(i)
                self.norm.append("")  # long line: never a heading

    def find(self, entry: TocEntry, after_line: int):
        """Earliest ``(line, last_line, form_rank)`` matching the entry."""
        first = _bisect(self.idx, after_line)
        best = None
        for k in range(first, len(self.idx)):
            if best is not None:
                break
            for rank, form in enumerate(entry.forms):
                last = self._match_at(k, form)
                if last is not None:
                    best = (k, last, rank)
                    break
        if best is None:
            return None
        k, last, rank = best
        if rank > 0:
            better = self._full_form_nearby(k, entry.forms[0])
            if better is not None:
                k, last = better
        return self.idx[k], self.idx[last]

    def _match_at(self, k: int, form: str) -> int | None:
        if not form:
            return None
        joined = ""
        for width in range(MAX_WINDOW):
            if k + width >= len(self.norm) or not self.norm[k + width]:
                return None
            joined = f"{joined} {self.norm[k + width]}".strip()
            if joined == form or _is_truncation(form, joined):
                return k + width
            if len(joined) > len(form) + PREFIX_SLACK:
                return None
        return None

    def _full_form_nearby(self, k: int, form: str):
        for j in range(k + 1, min(k + 1 + LOOKAHEAD_FULL_FORM, len(self.idx))):
            last = self._match_at(j, form)
            if last is not None:
                return j, last
        return None

    def number_marker_before(self, k_line: int) -> int | None:
        """Line of a bare ``Chapter 3`` marker right above ``k_line``."""
        k = _bisect(self.idx, k_line) - 1
        if k >= 0 and is_number_marker(self.norm[k]):
            return self.idx[k]
        return None


def _is_truncation(entry_form: str, body_form: str) -> bool:
    """TOC links are sometimes cut short: ``...Conques`` vs ``...Conquest``."""
    return (
        len(entry_form) >= MIN_PREFIX_CHARS
        and body_form.startswith(entry_form)
        and len(body_form) <= len(entry_form) + PREFIX_SLACK
    )


def _bisect(values: list[int], target: int) -> int:
    lo, hi = 0, len(values)
    while lo < hi:
        mid = (lo + hi) // 2
        if values[mid] < target:
            lo = mid + 1
        else:
            hi = mid
    return lo


def _complete_title(title: str, body_line: str) -> str:
    """Repair a title the TOC cut short using the heading in the text."""
    tail = title.split()[-1] if title.split() else ""
    at = body_line.rfind(tail) if tail else -1
    if at < 0:
        return title
    completed = title[: len(title) - len(tail)] + body_line[at:]
    if normalize(completed).startswith(normalize(title)):
        return completed
    return title


def _locate(
    lines: list[str], entries: list[TocEntry], toc_end: int
) -> list[Boundary] | None:
    body = _BodyIndex(lines, toc_end)
    boundaries: list[Boundary] = []
    cursor = toc_end
    for entry in entries:
        found = body.find(entry, cursor)
        if found is None:
            continue
        first, last = found
        start = first
        marker = body.number_marker_before(first)
        if marker is not None and marker >= cursor:
            start = marker
        boundaries.append(
            Boundary(
                start,
                last + 1,
                _complete_title(entry.title, strip_markdown(lines[last])),
                PART if entry.is_part else CHAPTER,
            )
        )
        cursor = last + 1

    chapter_entries = [e for e in entries if not e.is_part]
    chapters_found = [b for b in boundaries if b.kind == CHAPTER]
    if len(chapters_found) < 2 or (
        len(chapters_found) / max(len(chapter_entries), 1) < MIN_MATCH_RATIO
    ):
        return None
    return boundaries
