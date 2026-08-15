"""Per-node dossier pages and the node index."""

from __future__ import annotations

import html
from urllib.parse import quote

from ..codes import node_page_href, node_peer_key
from ..config import BuildConfig
from ..graph import NodeGraph
from ..templating import render_page, site_url
from .fragments import chain_link_list, node_link_list, render_node_source_html, resource_cards


def matrix_html(
    config: BuildConfig, graph: NodeGraph, current_node: dict, deps: list[dict], uses: list[dict]
) -> str:
    """Dependency-by-user grid for one node."""
    rows = deps[:28]
    cols = [{
        "href": node_page_href(current_node),
        "node_href": current_node["href"],
        "code": current_node["code"],
    }] + uses[:10]
    dep_sets = {col["node_href"]: {item["node_href"] for item in graph.direct_items(col["node_href"], "out")} for col in cols}
    head = "".join(
        f'<th><a href="{html.escape(site_url(config.base_path, col["href"]))}">{html.escape(col["code"])}</a></th>'
        for col in cols
    )
    body = []
    for row in rows:
        cells = "".join(
            f'<td class="{"has-edge" if row["node_href"] in dep_sets[col["node_href"]] else ""}">'
            f'{"use" if row["node_href"] in dep_sets[col["node_href"]] else ""}</td>'
            for col in cols
        )
        row_href = html.escape(site_url(config.base_path, row["href"]))
        body.append(f'<tr><th><a href="{row_href}">{html.escape(row["code"])}</a></th>{cells}</tr>')
    return f'<div class="matrix-scroll"><table class="usage-matrix"><thead><tr><th>Dependency</th>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'


def graph_html(config: BuildConfig, current_node: dict, deps: list[dict], uses: list[dict]) -> str:
    """Small SVG showing a node between its dependencies and its users."""
    left = deps[:10]
    right = uses[:10]
    height = max(210, 84 + max(len(left), len(right)) * 34)
    center_y = height // 2
    lines = []
    nodes = []
    for index, item in enumerate(left):
        y = 42 + index * 34
        lines.append(f'<line x1="144" y1="{y}" x2="220" y2="{center_y}" />')
        href = html.escape(site_url(config.base_path, item["href"]))
        nodes.append(f'<a href="{href}"><circle cx="90" cy="{y}" r="18" class="dep-node"/><text x="90" y="{y + 4}" text-anchor="middle">{html.escape(item["code"])}</text></a>')
    for index, item in enumerate(right):
        y = 42 + index * 34
        lines.append(f'<line x1="240" y1="{center_y}" x2="316" y2="{y}" />')
        href = html.escape(site_url(config.base_path, item["href"]))
        nodes.append(f'<a href="{href}"><circle cx="370" cy="{y}" r="18" class="use-node"/><text x="370" y="{y + 4}" text-anchor="middle">{html.escape(item["code"])}</text></a>')
    focus = f'<circle cx="230" cy="{center_y}" r="26" class="focus-node"/><text x="230" y="{center_y + 5}" text-anchor="middle">{html.escape(current_node["code"])}</text>'
    return f'<svg class="node-graph" viewBox="0 0 460 {height}" role="img" aria-label="Node dependency graph">{"".join(lines)}{"".join(nodes)}{focus}</svg>'


def write_node_pages(config: BuildConfig, graph: NodeGraph) -> None:
    """Write one dossier page per canonical Ethics node."""
    nodes_dir = config.output / "nodes"
    nodes_dir.mkdir(parents=True, exist_ok=True)
    peers_by_key: dict[tuple[int, str, str], list[dict]] = {}
    for peer in graph.ordered:
        peers_by_key.setdefault(node_peer_key(peer), []).append(peer)

    for node in graph.ordered:
        href = node["href"]
        deps = graph.direct_items(href, "out")
        uses = graph.direct_items(href, "in")
        notes, glossary, resources = graph.dossier_items(href)
        peers = peers_by_key[node_peer_key(node)]
        peer_index = next((i for i, peer in enumerate(peers) if peer["href"] == href), -1)
        previous_node = peers[peer_index - 1] if peer_index > 0 else None
        next_node = peers[peer_index + 1] if peer_index >= 0 and peer_index + 1 < len(peers) else None
        prev_link = (
            f'<a href="{site_url(config.base_path, node_page_href(previous_node))}">'
            f'Previous: {html.escape(previous_node["code"])}</a>'
            if previous_node else ""
        )
        next_link = (
            f'<a href="{site_url(config.base_path, node_page_href(next_node))}">'
            f'Next: {html.escape(next_node["code"])}</a>'
            if next_node else ""
        )
        page = render_page(
            config,
            "node.html",
            code=html.escape(node["code"]),
            type=html.escape(node["type"]),
            doc=html.escape(node["doc"]),
            source_href=html.escape(site_url(config.base_path, node["href"])),
            source_query=quote(node["href"], safe=""),
            page_href=site_url(config.base_path, node_page_href(node)),
            source_html=render_node_source_html(config, node),
            note_count=len(notes),
            glossary_count=len(glossary),
            resource_count=len(resources),
            notes=resource_cards(config, notes, "No linked editorial notes recorded for this node."),
            glossary=resource_cards(config, glossary, "No linked glossary terms recorded for this node."),
            resources=resource_cards(config, resources, "No other linked resources recorded for this node."),
            prev_link=prev_link,
            next_link=next_link,
            uses=node_link_list(config, deps, "No explicit dependencies recorded for this node."),
            used_by=node_link_list(config, uses, "No recorded uses of this node."),
            ancestors=chain_link_list(
                config, graph.transitive_items(href, "out"),
                "No transitive ancestors recorded.", node["code"], "out",
            ),
            descendants=chain_link_list(
                config, graph.transitive_items(href, "in"),
                "No transitive descendants recorded.", node["code"], "in",
            ),
            matrix=matrix_html(config, graph, node, deps, uses),
            graph=graph_html(config, node, deps, uses),
        )
        (nodes_dir / f"{node['code']}.html").write_text(page, encoding="utf-8")


def write_node_index(config: BuildConfig, stats: list[dict], edge_count: int) -> None:
    """Write the filterable table of every node."""
    nodes_dir = config.output / "nodes"
    nodes_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for row in stats:
        row_href = html.escape(site_url(config.base_path, row["href"]))
        rows.append(
            f'<tr data-search="{html.escape((row["code"] + " " + row["type"] + " " + row["part"] + " " + row["label"]).lower())}">'
            f'<td><a href="{row_href}">{html.escape(row["code"])}</a></td>'
            f'<td>{html.escape(row["type"])}</td><td>{html.escape(row["part"])}</td>'
            f'<td>{row["direct_uses"]}</td><td>{row["direct_used_by"]}</td>'
            f'<td>{row["ancestors"]}</td><td>{row["descendants"]}</td>'
            f'<td>{html.escape(row["label"])}</td></tr>'
        )

    page = render_page(
        config,
        "node-index.html",
        node_count=len(stats),
        edge_count=edge_count,
        rows="".join(rows),
    )
    (nodes_dir / "index.html").write_text(page, encoding="utf-8")
