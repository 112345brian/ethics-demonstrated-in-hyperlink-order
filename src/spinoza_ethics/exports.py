"""Machine-readable exports: the browser data payloads and the graph files."""

from __future__ import annotations

import csv
import json

from .codes import PART_LABELS, node_code_parts, node_page_href
from .config import CORE_FILES, BuildConfig
from .corpus import Corpus
from .graph import NodeGraph, edge_type_for
from .templating import static_text

#: Static assets copied verbatim into ``assets/``.
STATIC_ASSETS = ["site.css", "site.js", "app.js"]


def write_site_data(config: BuildConfig, corpus: Corpus) -> None:
    """Write the three ``window.SPINOZA_SITE_DATA`` payloads and static assets.

    The data is split across three files because the combined payload is large
    enough that a single script tag was awkward to serve.
    """
    assets = config.output / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    (assets / "site-data.js").write_text(
        "window.SPINOZA_SITE_DATA = " + json.dumps({
            "records": corpus.records,
            "anchors": corpus.anchors,
            "ethicsNodes": corpus.ethics_nodes,
            "nodeForAnchor": corpus.node_for_anchor,
            "coreFiles": CORE_FILES,
        }, ensure_ascii=False) + ";\n",
        encoding="utf-8",
    )
    (assets / "site-data-links.js").write_text(
        "Object.assign(window.SPINOZA_SITE_DATA, " + json.dumps({
            "backlinks": corpus.backlinks,
            "outgoing": corpus.outgoing,
        }, ensure_ascii=False) + ");\n",
        encoding="utf-8",
    )
    (assets / "site-data-search.js").write_text(
        "window.SPINOZA_SITE_DATA.search = " + json.dumps(corpus.search, ensure_ascii=False) + ";\n",
        encoding="utf-8",
    )
    for name in STATIC_ASSETS:
        (assets / name).write_text(static_text(name), encoding="utf-8")


def node_stats(graph: NodeGraph) -> list[dict]:
    """Per-node direct and transitive edge counts, in canonical order."""
    stats = []
    for node in graph.ordered:
        href = node["href"]
        part_order, _kind, _number = node_code_parts(node["code"])
        stats.append({
            "code": node["code"],
            "type": node["type"],
            "part": PART_LABELS.get(part_order, "Other"),
            "href": node_page_href(node),
            "source": href,
            "label": node["label"],
            "direct_uses": len(graph.direct_nodes(href, "out")),
            "direct_used_by": len(graph.direct_nodes(href, "in")),
            "ancestors": len(graph.transitive_items(href, "out")),
            "descendants": len(graph.transitive_items(href, "in")),
        })
    return stats


def edge_rows(graph: NodeGraph, corpus: Corpus) -> list[dict]:
    """Deduplicated node-to-node edges for the CSV and JSON exports."""
    rows: list[dict] = []
    seen: set[tuple] = set()
    for source, edges in corpus.outgoing.items():
        source_node = graph.by_href.get(graph.canonical(source))
        if not source_node:
            continue
        for edge in edges:
            target_node = graph.by_href.get(graph.canonical(edge.get("target", "")))
            if not target_node:
                continue
            row = {
                "source": source_node["code"],
                "source_href": node_page_href(source_node),
                "target": target_node["code"],
                "target_href": node_page_href(target_node),
                "type": edge_type_for(edge),
                "label": edge.get("label", ""),
                "via": edge.get("via", ""),
            }
            key = tuple(row.items())
            if key in seen:
                continue
            seen.add(key)
            rows.append(row)
    return rows


def write_graph_exports(config: BuildConfig, stats: list[dict], rows: list[dict]) -> None:
    """Write the node/edge CSVs and the combined graph JSON."""
    graph_dir = config.output / "graph"
    graph_dir.mkdir(parents=True, exist_ok=True)

    with (graph_dir / "ethics-nodes.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(stats[0].keys()))
        writer.writeheader()
        writer.writerows(stats)

    with (graph_dir / "ethics-edges.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=["source", "source_href", "target", "target_href", "type", "label", "via"]
        )
        writer.writeheader()
        writer.writerows(rows)

    (graph_dir / "ethics-graph.json").write_text(
        json.dumps({"nodes": stats, "edges": rows}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
