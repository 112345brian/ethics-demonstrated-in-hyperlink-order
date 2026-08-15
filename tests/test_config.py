"""Corpus layout constants and source-file discovery."""

from __future__ import annotations

from pathlib import Path

from spinoza_ethics.config import CORE_FILES, DOC_LABELS, ETHICS_FILES, BuildConfig


def source_with(tmp_path, names: list[str]) -> BuildConfig:
    text = tmp_path / "source" / "text"
    text.mkdir(parents=True)
    for name in names:
        (text / name).write_text("<html></html>", encoding="utf-8")
    return BuildConfig.create(source=tmp_path / "source", output=tmp_path / "build")


def test_files_are_sorted_with_titlepage_last(tmp_path):
    config = source_with(tmp_path, ["part0030.html", "part0029_split_000.html", "part0086.html"])
    assert config.files == [
        "text/part0029_split_000.html",
        "text/part0030.html",
        "text/part0086.html",
        "titlepage.xhtml",
    ]


def test_files_are_posix_relative_paths(tmp_path):
    config = source_with(tmp_path, ["part0030.html"])
    assert config.files[0] == "text/part0030.html"


def test_files_ignores_non_html_siblings(tmp_path):
    config = source_with(tmp_path, ["part0030.html"])
    (tmp_path / "source" / "text" / "notes.txt").write_text("x", encoding="utf-8")
    assert config.files == ["text/part0030.html", "titlepage.xhtml"]


def test_files_of_an_empty_source_is_just_the_titlepage(tmp_path):
    config = source_with(tmp_path, [])
    assert config.files == ["titlepage.xhtml"]


def test_create_resolves_paths_to_absolutes(tmp_path):
    config = BuildConfig.create(source="source", output="build")
    assert config.source.is_absolute() and config.output.is_absolute()


def test_create_accepts_path_objects(tmp_path):
    config = BuildConfig.create(source=Path(tmp_path), output=Path(tmp_path) / "build")
    assert config.source == Path(tmp_path).resolve()


def test_doc_label_known_file():
    config = BuildConfig.create(source=".", output=".")
    assert config.doc_label("text/part0030.html") == "Ethics II-III"


def test_doc_label_falls_back_for_unknown_file():
    config = BuildConfig.create(source=".", output=".")
    assert config.doc_label("text/part0099.html", "Untitled") == "Untitled"


def test_doc_label_default_fallback_is_empty():
    config = BuildConfig.create(source=".", output=".")
    assert config.doc_label("text/part0099.html") == ""


def test_every_core_file_has_a_label():
    assert not set(CORE_FILES) - set(DOC_LABELS)


def test_ethics_files_are_a_subset_of_the_core():
    assert ETHICS_FILES <= set(CORE_FILES)


def test_core_files_have_no_duplicates():
    assert len(CORE_FILES) == len(set(CORE_FILES))
