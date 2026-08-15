"""Build orchestration: run every stage in order and report what was produced."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from .config import COPIED_DIRS, COPIED_FILES, BuildConfig
from .corpus import Corpus, collect
from .database import write_database
from .exports import edge_rows, node_stats, write_graph_exports, write_site_data
from .graph import NodeGraph
from .pwa import write_pwa_files
from .render.documents import write_documents
from .render.nodes import write_node_index, write_node_pages
from .render.site import write_apparatus, write_index, write_resources
from .templating import template_text


class UnsafeOutputError(RuntimeError):
    """Raised when the output directory looks like something we must not wipe."""


def check_output_dir(output: Path) -> None:
    """Refuse to clean a directory that holds source rather than build output.

    The predecessor of this package wrote into the repository root and deleted
    everything it found there except itself, which would have destroyed the
    working tree's ``.git`` directory.
    """
    if not output.exists():
        return
    for guard in (".git", "pyproject.toml", "src"):
        if (output / guard).exists():
            raise UnsafeOutputError(
                f"refusing to clean {output}: it contains {guard!r} and looks like a "
                "source tree, not a build directory"
            )


def clean_output(config: BuildConfig) -> None:
    """Remove any previous build."""
    check_output_dir(config.output)
    if config.output.exists():
        shutil.rmtree(config.output)
    config.output.mkdir(parents=True)


def copy_source_assets(config: BuildConfig) -> None:
    """Copy images, fonts and the cover across from the source corpus."""
    for name in COPIED_DIRS:
        src_dir = config.source / name
        if src_dir.exists():
            shutil.copytree(src_dir, config.output / name, dirs_exist_ok=True)
    for name in COPIED_FILES:
        src_file = config.source / name
        if src_file.exists():
            shutil.copy2(src_file, config.output / name)
            if name == "cover.jpeg":
                shutil.copy2(src_file, config.output / "favicon.ico")


def build_report(config: BuildConfig, corpus: Corpus) -> dict:
    """Summary counts for the finished build."""
    return {
        "source": str(config.source),
        "output": str(config.output),
        "files": len(config.files),
        "anchors": len(corpus.anchors),
        "linked_targets": len([k for k, v in corpus.backlinks.items() if v]),
        "incoming_references": sum(len(v) for v in corpus.backlinks.values()),
        "outgoing_reference_sources": len(corpus.outgoing),
        "search_records": len(corpus.search),
        "ethics_nodes": len(corpus.ethics_nodes),
        "node_anchor_mappings": len(corpus.node_for_anchor),
    }


def build(config: BuildConfig, clean: bool = True) -> dict:
    """Generate the whole site and return the build report."""
    if clean:
        clean_output(config)
    (config.output / "text").mkdir(parents=True, exist_ok=True)

    corpus = collect(config)
    graph = NodeGraph(corpus)

    write_site_data(config, corpus)
    write_index(config, corpus)
    write_apparatus(config, corpus)
    write_node_pages(config, graph)

    stats = node_stats(graph)
    rows = edge_rows(graph, corpus)
    write_graph_exports(config, stats, rows)
    write_node_index(config, stats, len(rows))
    write_resources(config)

    write_database(config, corpus)
    (config.output / "GRAPH_MODEL.md").write_text(
        template_text("GRAPH_MODEL.md"), encoding="utf-8"
    )

    write_documents(config)
    copy_source_assets(config)

    # Must be last: the service worker precaches whatever it finds on disk.
    write_pwa_files(config)

    report = build_report(config, corpus)
    (config.output / "build-report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    return report
