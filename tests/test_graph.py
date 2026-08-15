"""Edge classification and traversal over a small hand-built node graph."""

from __future__ import annotations

from spinoza_ethics.corpus import Corpus
from spinoza_ethics.graph import NodeGraph, edge_type_for

FILE = "text/part0029_split_001.html"


def href_for(code: str) -> str:
    return f"/{FILE}#cite-{code}"


def make_node(code: str, node_type: str = "proposition") -> dict:
    return {
        "href": href_for(code),
        "id": f"cite-{code}",
        "file": FILE,
        "doc": "Ethics I-II",
        "type": node_type,
        "label": f"{code}: label text",
        "code": code,
    }


def edge(target: str, source: str, classes: str = "cite", label: str = "P1") -> dict:
    return {
        "target": target,
        "from": source,
        "file": FILE,
        "doc": "Ethics I-II",
        "label": label,
        "classes": classes,
    }


def make_corpus(nodes, outgoing=None, backlinks=None, node_for_anchor=None) -> Corpus:
    return Corpus(
        ethics_nodes=list(nodes),
        outgoing=dict(outgoing or {}),
        backlinks=dict(backlinks or {}),
        node_for_anchor=dict(node_for_anchor or {}),
    )


# --- edge_type_for -------------------------------------------------------


def test_edge_type_cite():
    assert edge_type_for({"classes": "cite reference-link", "target": "/text/a.html"}) == "cites"


def test_edge_type_gloss():
    assert edge_type_for({"classes": "gloss", "target": "/text/a.html"}) == "glosses"


def test_edge_type_noteref():
    assert edge_type_for({"classes": "noteref", "target": "/text/a.html"}) == "note-ref"


def test_edge_type_backlink():
    assert edge_type_for({"classes": "backlink", "target": "/text/a.html"}) == "backlink"


def test_edge_type_falls_through_to_links_to_for_internal_text_target():
    assert edge_type_for({"classes": "", "target": "/text/part0033.html#note-9"}) == "links-to"


def test_edge_type_external_for_offsite_target():
    assert edge_type_for({"classes": "", "target": "https://example.com/a"}) == "external"


def test_edge_type_handles_missing_keys():
    assert edge_type_for({}) == "external"


def test_edge_type_handles_none_classes():
    assert edge_type_for({"classes": None, "target": "/text/a.html"}) == "links-to"


# --- NodeGraph basics ----------------------------------------------------


def test_ordered_nodes_use_canonical_sort():
    corpus = make_corpus([make_node("IP10"), make_node("ID1"), make_node("IP2")])
    graph = NodeGraph(corpus)
    assert [n["code"] for n in graph.ordered] == ["ID1", "IP2", "IP10"]


def test_canonical_resolves_anchor_to_containing_node():
    corpus = make_corpus(
        [make_node("IP1")],
        node_for_anchor={f"/{FILE}#para-9": href_for("IP1")},
    )
    graph = NodeGraph(corpus)
    assert graph.canonical(f"/{FILE}#para-9") == href_for("IP1")


def test_canonical_passes_unknown_href_through():
    graph = NodeGraph(make_corpus([make_node("IP1")]))
    assert graph.canonical("/text/part0033.html#note-9") == "/text/part0033.html#note-9"


# --- direct_nodes --------------------------------------------------------


def test_direct_nodes_outgoing():
    p1, p2 = make_node("IP1"), make_node("IP2")
    corpus = make_corpus(
        [p1, p2],
        outgoing={p2["href"]: [edge(p1["href"], p2["href"])]},
    )
    assert [n["code"] for n in NodeGraph(corpus).direct_nodes(p2["href"], "out")] == ["IP1"]


def test_direct_nodes_incoming():
    p1, p2 = make_node("IP1"), make_node("IP2")
    corpus = make_corpus(
        [p1, p2],
        backlinks={p1["href"]: [{"from": p2["href"], "classes": "cite", "label": "P2"}]},
    )
    assert [n["code"] for n in NodeGraph(corpus).direct_nodes(p1["href"], "in")] == ["IP2"]


def test_direct_nodes_deduplicates_repeated_edges():
    p1, p2 = make_node("IP1"), make_node("IP2")
    corpus = make_corpus(
        [p1, p2],
        outgoing={p2["href"]: [edge(p1["href"], p2["href"])] * 3},
    )
    assert len(NodeGraph(corpus).direct_nodes(p2["href"], "out")) == 1


def test_direct_nodes_deduplicates_via_anchor_aliases():
    """Two edges reaching the same node through different anchors collapse to one."""
    p1, p2 = make_node("IP1"), make_node("IP2")
    alias = f"/{FILE}#para-9"
    corpus = make_corpus(
        [p1, p2],
        outgoing={p2["href"]: [edge(p1["href"], p2["href"]), edge(alias, p2["href"])]},
        node_for_anchor={alias: p1["href"]},
    )
    assert len(NodeGraph(corpus).direct_nodes(p2["href"], "out")) == 1


def test_direct_nodes_skips_targets_that_are_not_nodes():
    p1 = make_node("IP1")
    corpus = make_corpus(
        [p1],
        outgoing={p1["href"]: [edge("/text/part0033.html#note-9", p1["href"], "noteref")]},
    )
    assert NodeGraph(corpus).direct_nodes(p1["href"], "out") == []


def test_direct_nodes_of_unknown_href_is_empty():
    graph = NodeGraph(make_corpus([make_node("IP1")]))
    assert graph.direct_nodes("/text/nowhere.html#x", "out") == []


def test_direct_items_are_render_ready():
    p1, p2 = make_node("IP1"), make_node("IP2")
    corpus = make_corpus([p1, p2], outgoing={p2["href"]: [edge(p1["href"], p2["href"])]})
    item = NodeGraph(corpus).direct_items(p2["href"], "out")[0]
    assert item == {
        "href": "/nodes/IP1.html",
        "node_href": p1["href"],
        "code": "IP1",
        "text": "IP1",
        "kind": "proposition",
        "doc": p1["label"],
    }


# --- transitive_items ----------------------------------------------------


def chain_corpus() -> Corpus:
    """IP3 -> IP2 -> IP1 (each node cites the previous one)."""
    p1, p2, p3 = make_node("IP1"), make_node("IP2"), make_node("IP3")
    return make_corpus(
        [p1, p2, p3],
        outgoing={
            p3["href"]: [edge(p2["href"], p3["href"])],
            p2["href"]: [edge(p1["href"], p2["href"])],
        },
        backlinks={
            p2["href"]: [{"from": p3["href"], "classes": "cite", "label": "P3"}],
            p1["href"]: [{"from": p2["href"], "classes": "cite", "label": "P2"}],
        },
    )


def test_transitive_items_records_depth():
    rows = NodeGraph(chain_corpus()).transitive_items(href_for("IP3"), "out")
    assert [(r["code"], r["depth"]) for r in rows] == [("IP2", 1), ("IP1", 2)]


def test_transitive_items_records_path():
    rows = NodeGraph(chain_corpus()).transitive_items(href_for("IP3"), "out")
    assert [r["path"] for r in rows] == [["IP2"], ["IP2", "IP1"]]


def test_transitive_items_walks_backlinks_in_the_other_direction():
    rows = NodeGraph(chain_corpus()).transitive_items(href_for("IP1"), "in")
    assert [(r["code"], r["depth"]) for r in rows] == [("IP2", 1), ("IP3", 2)]


def test_transitive_items_honours_max_depth():
    rows = NodeGraph(chain_corpus()).transitive_items(href_for("IP3"), "out", max_depth=1)
    assert [r["code"] for r in rows] == ["IP2"]


def test_transitive_items_max_depth_zero_returns_nothing():
    assert NodeGraph(chain_corpus()).transitive_items(href_for("IP3"), "out", max_depth=0) == []


def test_transitive_items_terminates_on_a_cycle():
    """A -> B -> A must not loop forever, and must not revisit the start."""
    p1, p2 = make_node("IP1"), make_node("IP2")
    corpus = make_corpus(
        [p1, p2],
        outgoing={
            p1["href"]: [edge(p2["href"], p1["href"])],
            p2["href"]: [edge(p1["href"], p2["href"])],
        },
    )
    rows = NodeGraph(corpus).transitive_items(p1["href"], "out")
    assert [r["code"] for r in rows] == ["IP2"]


def test_transitive_items_terminates_on_a_self_loop():
    p1 = make_node("IP1")
    corpus = make_corpus([p1], outgoing={p1["href"]: [edge(p1["href"], p1["href"])]})
    assert NodeGraph(corpus).transitive_items(p1["href"], "out") == []


def test_transitive_items_visits_each_node_once_in_a_diamond():
    p1, p2, p3, p4 = (make_node(c) for c in ("IP1", "IP2", "IP3", "IP4"))
    corpus = make_corpus(
        [p1, p2, p3, p4],
        outgoing={
            p4["href"]: [edge(p2["href"], p4["href"]), edge(p3["href"], p4["href"])],
            p2["href"]: [edge(p1["href"], p2["href"])],
            p3["href"]: [edge(p1["href"], p3["href"])],
        },
    )
    rows = NodeGraph(corpus).transitive_items(p4["href"], "out")
    assert [r["code"] for r in rows] == ["IP2", "IP3", "IP1"]


# --- dossier_items -------------------------------------------------------


def dossier_corpus() -> tuple[NodeGraph, str]:
    p1, p2 = make_node("IP1"), make_node("IP2")
    edges = [
        edge(p2["href"], p1["href"]),  # a node edge: excluded from the dossier
        edge("/text/part0033.html#note-12", p1["href"], "noteref", "note 12"),
        edge("/text/part0035_split_000.html#g-cause", p1["href"], "gloss", "cause"),
        edge("/text/part0039.html#ref-1", p1["href"], "", "Reference List"),
        edge("https://example.com/", p1["href"], "", "offsite"),
    ]
    corpus = make_corpus([p1, p2], outgoing={p1["href"]: edges})
    return NodeGraph(corpus), p1["href"]


def test_dossier_notes():
    graph, href = dossier_corpus()
    notes, _, _ = graph.dossier_items(href)
    assert [n["title"] for n in notes] == ["Note note 12"]


def test_dossier_glossary():
    graph, href = dossier_corpus()
    _, glossary, _ = graph.dossier_items(href)
    assert [g["title"] for g in glossary] == ["Glossary: cause"]


def test_dossier_resources():
    graph, href = dossier_corpus()
    _, _, resources = graph.dossier_items(href)
    assert [r["href"] for r in resources] == ["/text/part0039.html#ref-1"]


def test_dossier_excludes_node_targets_and_external_links():
    graph, href = dossier_corpus()
    everything = [item["href"] for group in graph.dossier_items(href) for item in group]
    assert href_for("IP2") not in everything
    assert "https://example.com/" not in everything


def test_dossier_treats_the_notes_document_as_notes_regardless_of_class():
    p1 = make_node("IP1")
    corpus = make_corpus(
        [p1],
        outgoing={p1["href"]: [edge("/text/part0033.html#n-3", p1["href"], "", "3")]},
    )
    notes, _, resources = NodeGraph(corpus).dossier_items(p1["href"])
    assert [n["title"] for n in notes] == ["Note 3"] and resources == []


def test_dossier_of_a_node_with_no_outgoing_edges_is_empty():
    graph = NodeGraph(make_corpus([make_node("IP1")]))
    assert graph.dossier_items(href_for("IP1")) == ([], [], [])
