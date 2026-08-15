"""Traversal over the Ethics node graph.

The legacy script carried two near-identical copies of this logic (one
returning render-ready dicts for the node pages, one returning bare hrefs for
the CSV/JSON exports).  Both are expressed here in terms of a single
:meth:`NodeGraph.direct_nodes` walk.
"""

from __future__ import annotations

from .codes import node_page_href, node_sort_key
from .corpus import Corpus

MAX_CHAIN_DEPTH = 8


def edge_type_for(edge: dict) -> str:
    """Classify a link into one of the graph's edge types."""
    classes = set((edge.get("classes") or "").split())
    target = edge.get("target", "")
    if "cite" in classes:
        return "cites"
    if "gloss" in classes:
        return "glosses"
    if "noteref" in classes:
        return "note-ref"
    if "backlink" in classes:
        return "backlink"
    if target.startswith("/text/"):
        return "links-to"
    return "external"


class NodeGraph:
    """Canonical Ethics nodes plus the edges between them."""

    def __init__(self, corpus: Corpus) -> None:
        self.by_href = {node["href"]: node for node in corpus.ethics_nodes}
        self.ordered = sorted(corpus.ethics_nodes, key=node_sort_key)
        self._outgoing = corpus.outgoing
        self._backlinks = corpus.backlinks
        self._node_for_anchor = corpus.node_for_anchor

    def canonical(self, href: str) -> str:
        """Resolve an anchor href to the Ethics node that contains it."""
        return self._node_for_anchor.get(href, href)

    def direct_nodes(self, node_href: str, direction: str) -> list[dict]:
        """Immediate neighbours, deduplicated, in document order.

        ``direction`` is ``"out"`` for nodes this one uses, ``"in"`` for nodes
        that use it.
        """
        if direction == "out":
            edges = self._outgoing.get(node_href, [])
            key = "target"
        else:
            edges = self._backlinks.get(node_href, [])
            key = "from"
        seen: set[str] = set()
        result: list[dict] = []
        for edge in edges:
            ref = self.canonical(edge.get(key, ""))
            node = self.by_href.get(ref)
            if not node or ref in seen:
                continue
            seen.add(ref)
            result.append(node)
        return result

    def direct_items(self, node_href: str, direction: str) -> list[dict]:
        """:meth:`direct_nodes` as render-ready link items."""
        return [self.as_item(node) for node in self.direct_nodes(node_href, direction)]

    def transitive_items(
        self, start_href: str, direction: str, max_depth: int = MAX_CHAIN_DEPTH
    ) -> list[dict]:
        """Breadth-first walk recording the path taken to each node."""
        queue: list[tuple[str, int, list[str]]] = [(start_href, 0, [])]
        seen = {start_href}
        rows: list[dict] = []
        while queue:
            current, depth, path = queue.pop(0)
            if depth >= max_depth:
                continue
            for item in self.direct_items(current, direction):
                ref = item["node_href"]
                if ref in seen:
                    continue
                seen.add(ref)
                next_path = path + [item["code"]]
                row = dict(item)
                row["depth"] = depth + 1
                row["path"] = next_path
                rows.append(row)
                queue.append((ref, depth + 1, next_path))
        return rows

    def dossier_items(self, node_href: str) -> tuple[list[dict], list[dict], list[dict]]:
        """Split a node's non-node links into notes, glossary and other."""
        notes: list[dict] = []
        glossary: list[dict] = []
        resources: list[dict] = []
        for edge in self._outgoing.get(node_href, []):
            target = edge.get("target", "")
            if self.canonical(target) in self.by_href:
                continue
            kind = edge_type_for(edge)
            item = {
                "href": target,
                "title": edge.get("label") or target,
                "label": edge.get("label") or target,
            }
            if "part0033.html" in target or kind == "note-ref":
                item["title"] = f"Note {item['title']}"
                notes.append(item)
            elif kind == "glosses":
                item["title"] = f"Glossary: {item['title']}"
                glossary.append(item)
            elif target.startswith("/text/"):
                resources.append(item)
        return notes, glossary, resources

    @staticmethod
    def as_item(node: dict) -> dict:
        return {
            "href": node_page_href(node),
            "node_href": node["href"],
            "code": node["code"],
            "text": node["code"],
            "kind": node["type"],
            "doc": node["label"],
        }
