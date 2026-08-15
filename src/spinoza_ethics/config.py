"""Build configuration: input/output locations and the corpus layout constants.

The source corpus is a Calibre-exported EPUB of *The Collected Works of
Spinoza* (Curley translation).  Only a subset of its files is treated as the
Ethics-focused "core"; the rest is carried along as reference context.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

#: Files that make up the Ethics-focused core of the site.
CORE_FILES = [
    "text/part0029_split_000.html",  # Editorial Preface
    "text/part0029_split_001.html",  # Ethics I-II
    "text/part0030.html",            # Ethics II-III
    "text/part0031.html",            # Ethics III-IV
    "text/part0032.html",            # Ethics IV-V
    "text/part0033.html",            # Editorial Notes to Ethics
    "text/part0034.html",            # Glossary-Index preface / English-Latin-Dutch
    "text/part0035_split_000.html",
    "text/part0035_split_001.html",
    "text/part0036_split_000.html",
    "text/part0036_split_001.html",
    "text/part0037_split_000.html",
    "text/part0037_split_001.html",
    "text/part0037_split_002.html",
    "text/part0039.html",            # Reference List
    "text/part0086.html",            # Note on This EPUB
]

#: Human-readable labels for the core files.
DOC_LABELS = {
    "text/part0029_split_000.html": "Editorial Preface",
    "text/part0029_split_001.html": "Ethics I-II",
    "text/part0030.html": "Ethics II-III",
    "text/part0031.html": "Ethics III-IV",
    "text/part0032.html": "Ethics IV-V",
    "text/part0033.html": "Curley Notes",
    "text/part0034.html": "Glossary-Index",
    "text/part0035_split_000.html": "Glossary-Index",
    "text/part0035_split_001.html": "Latin-Dutch-English",
    "text/part0036_split_000.html": "Glossary-Index",
    "text/part0036_split_001.html": "Glossary-Index",
    "text/part0037_split_000.html": "Dutch-Latin-English",
    "text/part0037_split_001.html": "Dutch-Latin-English",
    "text/part0037_split_002.html": "Proper Names and Biblical References",
    "text/part0039.html": "Reference List",
    "text/part0086.html": "Editorial Note",
}

#: The files that contain the Ethics proper, where nodes are detected.
ETHICS_FILES = {
    "text/part0029_split_001.html",
    "text/part0030.html",
    "text/part0031.html",
    "text/part0032.html",
}

HTML_NS = "http://www.w3.org/1999/xhtml"

DEFAULT_SOURCE = Path("/tmp/spinoza_work")
DEFAULT_OUTPUT = Path(__file__).resolve().parents[2] / "build"

#: Asset directories copied verbatim from the source corpus.
COPIED_DIRS = ["images", "fonts"]

#: Single files copied verbatim from the source corpus.
COPIED_FILES = ["cover.jpeg"]


@dataclass(frozen=True)
class BuildConfig:
    """Where the build reads from and writes to."""

    source: Path
    output: Path

    @classmethod
    def create(cls, source: Path | str, output: Path | str) -> BuildConfig:
        return cls(source=Path(source).resolve(), output=Path(output).resolve())

    @property
    def files(self) -> list[str]:
        """Every source document, in stable build order."""
        found = sorted(
            path.relative_to(self.source).as_posix()
            for path in (self.source / "text").glob("*.html")
        )
        found.append("titlepage.xhtml")
        return found

    def doc_label(self, rel: str, fallback: str = "") -> str:
        return DOC_LABELS.get(rel, fallback)
