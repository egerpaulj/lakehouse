"""EPUBs whose chapter headings are links back to the table of contents.

``[1](contents.xhtml#c_ch1)`` / ``[Chapter title](contents.xhtml#c_ch1)``
"""

from __future__ import annotations

import re
from collections import Counter

from ..text_utils import is_part_title, normalize, strip_markdown
from .base import CHAPTER, PART, Boundary
from .toc import join_title

_LINK_LINE = re.compile(r"^\s*\[([^\]!][^\]]*)\]\(([^)\s]+#[^)\s]+)\)\s*$")
MAX_GAP = 3
DENSE_LINES = 8
MIN_AVG_CHARS = 800


class BacklinkHeadingSplitter:
    name = "backlink_headings"

    def find_boundaries(self, lines: list[str]) -> list[Boundary] | None:
        groups = _group(lines)
        groups = _drop_dense(groups)
        if not groups:
            return None
        target = Counter(g[1].split("#")[0] for g in groups).most_common(1)
        groups = [g for g in groups if g[1].split("#")[0] == target[0][0]]
        total = sum(len(line) for line in lines)
        if len(groups) < 3 or total / len(groups) < MIN_AVG_CHARS:
            return None
        boundaries = []
        for start, _, texts, last in groups:
            name = join_title(texts)
            kind = PART if is_part_title(normalize(name)) else CHAPTER
            boundaries.append(Boundary(start, last + 1, name, kind))
        return boundaries


def _group(lines: list[str]) -> list[tuple[int, str, list[str], int]]:
    """``(first line, href, texts, last line)`` per heading."""
    groups: list[tuple[int, str, list[str], int]] = []
    for i, line in enumerate(lines):
        match = _LINK_LINE.match(line)
        if not match:
            continue
        text, href = strip_markdown(match.group(1)), match.group(2)
        if not text:
            continue
        if groups and groups[-1][1] == href and i - groups[-1][3] <= MAX_GAP:
            groups[-1][2].append(text)
            groups[-1] = (*groups[-1][:3], i)
        else:
            groups.append((i, href, [text], i))
    return groups


def _drop_dense(groups):
    """A table of contents lists many targets within a few lines."""

    def close(a, b):
        return abs(a[0] - b[0]) <= DENSE_LINES

    return [
        g
        for k, g in enumerate(groups)
        if not (k > 0 and close(g, groups[k - 1]))
        and not (k + 1 < len(groups) and close(g, groups[k + 1]))
    ]
