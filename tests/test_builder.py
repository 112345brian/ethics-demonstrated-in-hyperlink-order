"""Guards around the destructive part of the build.

``clean_output`` does ``shutil.rmtree(config.output)``.  The predecessor of
this package pointed that at the repository root and deleted the working tree,
``.git`` included.  ``check_output_dir`` exists solely to make that impossible,
so these tests pin the exact markers it refuses on.
"""

from __future__ import annotations

import pytest

from spinoza_ethics.builder import (
    UnsafeOutputError,
    build_report,
    check_output_dir,
    clean_output,
)
from spinoza_ethics.config import BuildConfig
from spinoza_ethics.corpus import Corpus


@pytest.mark.parametrize("guard", [".git", "pyproject.toml", "src"])
def test_refuses_a_directory_holding_a_source_marker_file(tmp_path, guard):
    (tmp_path / guard).write_text("x", encoding="utf-8")
    with pytest.raises(UnsafeOutputError):
        check_output_dir(tmp_path)


@pytest.mark.parametrize("guard", [".git", "src"])
def test_refuses_a_directory_holding_a_source_marker_directory(tmp_path, guard):
    (tmp_path / guard).mkdir()
    with pytest.raises(UnsafeOutputError):
        check_output_dir(tmp_path)


def test_error_message_names_the_offending_marker(tmp_path):
    (tmp_path / ".git").mkdir()
    with pytest.raises(UnsafeOutputError, match=r"\.git"):
        check_output_dir(tmp_path)


def test_allows_a_plain_empty_directory(tmp_path):
    check_output_dir(tmp_path)


def test_allows_a_directory_holding_only_previous_build_output(tmp_path):
    (tmp_path / "index.html").write_text("<html></html>", encoding="utf-8")
    (tmp_path / "text").mkdir()
    check_output_dir(tmp_path)


def test_allows_a_path_that_does_not_exist(tmp_path):
    check_output_dir(tmp_path / "build")


def test_clean_output_refuses_to_wipe_a_source_tree(tmp_path):
    """The regression this whole guard exists for: never rmtree the repo."""
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    (repo / "src").mkdir()
    (repo / "pyproject.toml").write_text("[project]", encoding="utf-8")
    config = BuildConfig.create(source=tmp_path / "source", output=repo)

    with pytest.raises(UnsafeOutputError):
        clean_output(config)

    assert (repo / ".git").exists()
    assert (repo / "pyproject.toml").exists()
    assert (repo / "src").exists()


def test_clean_output_replaces_a_previous_build(tmp_path):
    output = tmp_path / "build"
    (output / "nodes").mkdir(parents=True)
    (output / "nodes" / "IP1.html").write_text("old", encoding="utf-8")
    config = BuildConfig.create(source=tmp_path / "source", output=output)

    clean_output(config)

    assert output.is_dir()
    assert list(output.iterdir()) == []


def test_clean_output_creates_a_missing_output_dir(tmp_path):
    output = tmp_path / "build"
    clean_output(BuildConfig.create(source=tmp_path / "source", output=output))
    assert output.is_dir()


# --- build_report --------------------------------------------------------


def report_fixture(tmp_path) -> dict:
    text = tmp_path / "source" / "text"
    text.mkdir(parents=True)
    (text / "part0030.html").write_text("<html></html>", encoding="utf-8")
    config = BuildConfig.create(source=tmp_path / "source", output=tmp_path / "build")
    corpus = Corpus(
        records=[{"file": "text/part0030.html"}],
        anchors={"/text/part0030.html#a": {}, "/text/part0030.html#b": {}},
        backlinks={"/text/part0030.html#a": [{}, {}], "/text/part0030.html#b": []},
        outgoing={"/text/part0030.html#c": [{}]},
        search=[{}, {}, {}],
        ethics_nodes=[{"code": "IIP1"}],
        node_for_anchor={"/text/part0030.html#a": "/text/part0030.html#cite-IIP1"},
    )
    return build_report(config, corpus)


def test_build_report_counts_source_files(tmp_path):
    assert report_fixture(tmp_path)["files"] == 2  # part0030.html + titlepage.xhtml


def test_build_report_counts_anchors(tmp_path):
    assert report_fixture(tmp_path)["anchors"] == 2


def test_build_report_linked_targets_excludes_empty_backlink_lists(tmp_path):
    assert report_fixture(tmp_path)["linked_targets"] == 1


def test_build_report_sums_incoming_references(tmp_path):
    assert report_fixture(tmp_path)["incoming_references"] == 2


def test_build_report_records_the_remaining_counts(tmp_path):
    report = report_fixture(tmp_path)
    assert (
        report["outgoing_reference_sources"],
        report["search_records"],
        report["ethics_nodes"],
        report["node_anchor_mappings"],
    ) == (1, 3, 1, 1)


def test_build_report_records_the_paths_as_strings(tmp_path):
    report = report_fixture(tmp_path)
    assert report["source"].endswith("source") and report["output"].endswith("build")
