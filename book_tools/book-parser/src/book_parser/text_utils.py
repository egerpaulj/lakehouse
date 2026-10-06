"""Text normalisation helpers shared by the chapter splitters."""

from __future__ import annotations

import re
import unicodedata

_LINK = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
_MD_NOISE = re.compile(r"[*_`>|#\\]+")
_NON_ALNUM = re.compile(r"[^0-9a-z]+")
_LETTER_DIGIT = re.compile(r"(?<=[a-z])(?=[0-9])|(?<=[0-9])(?=[a-z])")

_UNITS = (
    "one two three four five six seven eight nine ten eleven twelve "
    "thirteen fourteen fifteen sixteen seventeen eighteen nineteen"
).split()
_TENS = "twenty thirty forty fifty sixty seventy eighty ninety".split()
NUMBER_WORDS: dict[str, int] = {w: i + 1 for i, w in enumerate(_UNITS)}
NUMBER_WORDS.update({w: (i + 2) * 10 for i, w in enumerate(_TENS)})
NUMBER_WORDS["first"] = 1
NUMBER_WORDS["second"] = 2
NUMBER_WORDS["third"] = 3

# Roman numerals up to 39; longer ones are rare for chapters and clash with
# ordinary words.
_ROMAN = re.compile(r"^(x{0,3})(ix|iv|v?i{0,3})$")
_ROMAN_VALUES = {"i": 1, "v": 5, "x": 10}


def strip_markdown(text: str) -> str:
    """Remove links, emphasis and heading markers from one line."""
    text = _LINK.sub(r"\1", text)
    text = _MD_NOISE.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize(text: str) -> str:
    """Lower-case alphanumeric words separated by single spaces."""
    text = unicodedata.normalize("NFKD", strip_markdown(text))
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.replace("&", " and ").casefold()
    text = re.sub(r"['’‘`]", "", text)
    text = _NON_ALNUM.sub(" ", text)
    return _LETTER_DIGIT.sub(" ", text).strip()


def roman_to_int(token: str) -> int | None:
    if not token or not _ROMAN.match(token):
        return None
    total = 0
    for i, ch in enumerate(token):
        value = _ROMAN_VALUES[ch]
        nxt = _ROMAN_VALUES.get(token[i + 1]) if i + 1 < len(token) else None
        total += -value if nxt and nxt > value else value
    return total


def token_to_int(token: str) -> int | None:
    """Value of a normalised number token (``12``, ``iv``, ``seven``)."""
    if token.isdigit():
        return int(token) if len(token) <= 3 else None
    if token in NUMBER_WORDS:
        return NUMBER_WORDS[token]
    return roman_to_int(token)


def parse_number(tokens: list[str]) -> tuple[int, int] | None:
    """Parse a leading number; returns ``(value, tokens_used)``."""
    if not tokens:
        return None
    first = token_to_int(tokens[0])
    if first is None:
        return None
    if tokens[0] in _TENS_WORDS and len(tokens) > 1:
        second = NUMBER_WORDS.get(tokens[1])
        if second is not None and second < 10:
            return first + second, 2
    return first, 1


_TENS_WORDS = set(_TENS)


def strip_number_prefix(norm: str) -> tuple[str, int | None]:
    """Drop a leading ``chapter 3`` / ``IV`` / ``twenty one`` marker.

    Returns the remaining normalised text and the number that was removed.
    """
    tokens = norm.split()
    if tokens and tokens[0] in ("chapter", "chap"):
        tokens = tokens[1:]
    parsed = parse_number(tokens)
    if parsed is None:
        return " ".join(tokens), None
    value, used = parsed
    return " ".join(tokens[used:]), value


def canonical(norm: str) -> str:
    """Spell a leading number as digits: ``chapter two x`` -> ``2 x``."""
    rest, value = strip_number_prefix(norm)
    if value is None:
        return norm
    return f"{value} {rest}".strip()


def is_number_marker(norm: str) -> bool:
    """True for lines such as ``chapter 3``, ``iv`` or ``twelve``."""
    if not norm:
        return False
    rest, value = strip_number_prefix(norm)
    return value is not None and not rest


PART_RE = re.compile(r"^(part|book|volume|section)\s+(\S+)")


def is_part_title(norm: str) -> bool:
    match = PART_RE.match(norm)
    if not match:
        return False
    return token_to_int(match.group(2)) is not None
