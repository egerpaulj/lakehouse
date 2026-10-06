"""Document -> Markdown conversion."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Protocol

# Every extension a markitdown 0.1.x converter accepts. Images and audio need
# optional system tools (exiftool, ffmpeg) or an LLM; without them the
# conversion fails and the file is moved to ``failed/``.
SUPPORTED_EXTENSIONS = frozenset(
    {
        ".pdf",
        ".epub",
        ".docx",
        ".pptx",
        ".xlsx",
        ".xls",
        ".html",
        ".htm",
        ".csv",
        ".json",
        ".jsonl",
        ".xml",
        ".rss",
        ".atom",
        ".txt",
        ".text",
        ".md",
        ".markdown",
        ".ipynb",
        ".msg",
        ".zip",
        ".jpg",
        ".jpeg",
        ".png",
        ".wav",
        ".mp3",
        ".m4a",
        ".mp4",
    }
)
_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")


class DocumentConverter(Protocol):
    def convert(self, path: Path) -> str:
        """Return the document as Markdown."""


class MarkItDownConverter:
    """Uses https://github.com/microsoft/markitdown."""

    def __init__(self, markitdown=None):
        self._markitdown = markitdown

    def convert(self, path: Path) -> str:
        if self._markitdown is None:
            from markitdown import MarkItDown

            self._markitdown = MarkItDown(enable_plugins=False)
        text = self._markitdown.convert(str(path)).text_content
        return _IMAGE.sub("", text).replace("\r\n", "\n")
