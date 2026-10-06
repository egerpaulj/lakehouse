"""Find documents waiting in the inbox folder."""

from __future__ import annotations

from pathlib import Path

from book_parser.converters import SUPPORTED_EXTENSIONS


class FolderScanner:
    def __init__(
        self,
        folder: str | Path,
        extensions: frozenset[str] = SUPPORTED_EXTENSIONS,
    ):
        self._folder = Path(folder)
        self._extensions = extensions

    def pending(self) -> list[Path]:
        """Supported files directly inside the folder, oldest name first.

        Sub-folders (``processed``, ``failed``) and hidden / temporary files
        (``.x``, ``~$x``, ``*.part``) are ignored.
        """
        if not self._folder.is_dir():
            return []
        return sorted(
            p
            for p in self._folder.iterdir()
            if p.is_file()
            and p.suffix.lower() in self._extensions
            and not p.name.startswith((".", "~$"))
        )
