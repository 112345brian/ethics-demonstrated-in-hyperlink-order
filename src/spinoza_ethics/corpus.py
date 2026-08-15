"""Extraction pass: read the source XHTML and build the reference graph.

A single traversal collects anchors, links, search records and canonical
Ethics nodes, which the renderers and the database writer then consume.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from .codes import (
    classify_ethics_node,
    initial_part_for_file,
    update_part_from_heading,
    visible_ethics_code,
)
from .config import DOC_LABELS, ETHICS_FILES, BuildConfig
from .xmlutil import graph_href, lname, parse, text_content


@dataclass
class Corpus:
    """Everything the extraction pass learned about the source documents."""

    records: list[dict] = field(default_factory=list)
    anchors: dict[str, dict] = field(default_factory=dict)
    backlinks: dict[str, list[dict]] = field(default_factory=dict)
    outgoing: dict[str, list[dict]] = field(default_factory=dict)
    search: list[dict] = field(default_factory=list)
    ethics_nodes: list[dict] = field(default_factory=list)
    node_for_anchor: dict[str, str] = field(default_factory=dict)


def collect(config: BuildConfig) -> Corpus:
    """Walk every source document and extract the reference graph."""
    records: list[dict] = []
    anchors: dict[str, dict] = {}
    backlinks: dict[str, list[dict]] = defaultdict(list)
    outgoing: dict[str, list[dict]] = defaultdict(list)
    search: list[dict] = []
    ethics_nodes: list[dict] = []
    node_for_anchor: dict[str, str] = {}

    for rel in config.files:
        tree = parse(config.source / rel)
        root = tree.getroot()
        title_el = root.find(".//{*}title")
        doc_title = text_content(title_el) if title_el is not None else DOC_LABELS[rel]
        body = root.find(".//{*}body")
        if body is None:
            continue
        parents = {child: parent for parent in body.iter() for child in list(parent)}
        node_by_code: dict[str, dict] = {}
        element_node_hrefs: dict[str, str] = {}
        current_part = initial_part_for_file(rel)

        for el in body.iter():
            el_text = text_content(el)
            if rel in ETHICS_FILES and lname(el.tag) in {"h1", "h2", "h3", "h4"}:
                current_part = update_part_from_heading(el_text, current_part)
            idv = el.attrib.get("id")
            if idv:
                raw_label = text_content(el)
                if not raw_label and parents.get(el) is not None:
                    raw_label = text_content(parents[el])
                label = raw_label[:180] or idv
                key = f"/{rel}#{idv}"
                anchors[key] = {
                    "href": key,
                    "id": idv,
                    "file": rel,
                    "doc": DOC_LABELS.get(rel, doc_title),
                    "label": label,
                    "kind": lname(el.tag),
                }
                node_type = classify_ethics_node(idv, label) if rel in ETHICS_FILES else ""
                if node_type:
                    code = idv.removeprefix("cite-")
                    if code in node_by_code:
                        element_node_hrefs[idv] = node_by_code[code]["href"]
                    else:
                        node = {
                            "href": key,
                            "id": idv,
                            "file": rel,
                            "doc": DOC_LABELS.get(rel, doc_title),
                            "type": node_type,
                            "label": label[:260],
                            "code": code,
                        }
                        ethics_nodes.append(node)
                        node_by_code[node["code"]] = node
                        element_node_hrefs[idv] = key
                if lname(el.tag) in {"p", "h1", "h2", "h3", "h4", "li"} and label:
                    search.append({
                        "href": key,
                        "doc": DOC_LABELS.get(rel, doc_title),
                        "text": label[:360],
                    })
                if rel in ETHICS_FILES and lname(el.tag) in {"p", "h1", "h2", "h3", "h4"}:
                    code, node_type = visible_ethics_code(el_text, current_part)
                    if code and code not in node_by_code:
                        canonical_id = idv
                        canonical_href = key
                        for child in el.iter():
                            child_id = child.attrib.get("id", "")
                            if child_id == f"cite-{code}":
                                canonical_id = child_id
                                canonical_href = f"/{rel}#{child_id}"
                                break
                        node = {
                            "href": canonical_href,
                            "id": canonical_id,
                            "file": rel,
                            "doc": DOC_LABELS.get(rel, doc_title),
                            "type": node_type,
                            "label": el_text[:260] or code,
                            "code": code,
                        }
                        ethics_nodes.append(node)
                        node_by_code[code] = node
                        element_node_hrefs[idv] = canonical_href
                        element_node_hrefs[canonical_id] = canonical_href

        current_ethics_node = None
        for el in body.iter():
            idv = el.attrib.get("id", "")
            if rel in ETHICS_FILES and idv in element_node_hrefs:
                current_ethics_node = element_node_hrefs[idv]
            if rel in ETHICS_FILES and idv and current_ethics_node:
                node_for_anchor[f"/{rel}#{idv}"] = current_ethics_node
            if rel in ETHICS_FILES and lname(el.tag) == "a" and idv.startswith("cite-"):
                current_ethics_node = f"/{rel}#{idv}"
            if lname(el.tag) != "a":
                continue
            a = el
            href = a.attrib.get("href", "")
            if not href:
                continue
            resolved = graph_href(rel, href)
            if not resolved.startswith("/text/"):
                continue
            label = text_content(a) or href
            source_id = None
            cursor = a
            while cursor is not None:
                if cursor.attrib.get("id"):
                    source_id = cursor.attrib.get("id")
                    break
                cursor = parents.get(cursor)
            source_href = current_ethics_node or (f"/{rel}" + (f"#{source_id}" if source_id else ""))
            link_record = {
                "target": resolved,
                "from": source_href,
                "file": rel,
                "doc": DOC_LABELS.get(rel, doc_title),
                "label": label[:120],
                "classes": a.attrib.get("class", ""),
            }
            backlinks[resolved].append({
                "from": source_href,
                "file": rel,
                "doc": DOC_LABELS.get(rel, doc_title),
                "label": label[:120],
                "classes": a.attrib.get("class", ""),
            })
            outgoing[source_href].append(link_record)

        headings = []
        for el in body.iter():
            if lname(el.tag) in {"h1", "h2", "h3", "h4"}:
                hid = el.attrib.get("id")
                headings.append({
                    "level": lname(el.tag),
                    "id": hid,
                    "text": text_content(el),
                })

        records.append({
            "file": rel,
            "title": DOC_LABELS.get(rel, doc_title),
            "headings": headings,
        })

    for source_href, edges in list(outgoing.items()):
        for edge in list(edges):
            target_node = node_for_anchor.get(edge["target"])
            if not target_node or target_node == edge["target"]:
                continue
            node_edge = dict(edge)
            node_edge["target"] = target_node
            node_edge["via"] = edge["target"]
            if node_edge not in outgoing[source_href]:
                outgoing[source_href].append(node_edge)
            back = {
                "from": edge["from"],
                "file": edge["file"],
                "doc": edge["doc"],
                "label": edge["label"],
                "classes": edge["classes"],
                "via": edge["target"],
            }
            if back not in backlinks[target_node]:
                backlinks[target_node].append(back)

    return Corpus(
        records=records,
        anchors=anchors,
        backlinks=dict(backlinks),
        outgoing=dict(outgoing),
        search=search,
        ethics_nodes=ethics_nodes,
        node_for_anchor=node_for_anchor,
    )
