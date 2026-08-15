"""Parsing and ordering of canonical Ethics node codes (``IP11``, ``IVD2``...).

Nodes are identified two ways: from ``cite-XXX`` anchor ids, and from visible
text such as ``P11:`` read against a running part counter.
"""

from __future__ import annotations

import re

PART_ORDER = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5}
PART_LABELS = {1: "Part I", 2: "Part II", 3: "Part III", 4: "Part IV", 5: "Part V"}


def classify_ethics_node(anchor_id: str, label: str) -> str:
    if not anchor_id.startswith("cite-"):
        return ""
    code = anchor_id.removeprefix("cite-")
    if "P" in code:
        if label.startswith("Dem") or "Dem.:" in label:
            return "demonstration"
        if "Schol" in label:
            return "scholium"
        if "Cor" in label:
            return "corollary"
        return "proposition"
    if re.search(r"(?:^|I|V)D\d", code):
        return "definition"
    if re.search(r"A\d", code):
        return "axiom"
    return "ethics-node"


def initial_part_for_file(rel: str) -> str:
    return {
        "text/part0029_split_001.html": "I",
        "text/part0030.html": "II",
        "text/part0031.html": "III",
        "text/part0032.html": "IV",
    }.get(rel, "")


def update_part_from_heading(text: str, current: str) -> str:
    low = text.lower()
    if "first part" in low:
        return "I"
    if "second part" in low:
        return "II"
    if "third part" in low:
        return "III"
    if "fourth part" in low:
        return "IV"
    if "fifth part" in low:
        return "V"
    return current


def visible_ethics_code(text: str, part: str) -> tuple[str, str]:
    if not part:
        return "", ""
    compact = re.sub(r"^(?:\[[^\]]+\]\s*)+", "", text.strip())
    match = re.match(r"^(D|A|P)(\d+)\b", compact)
    if not match:
        return "", ""
    kind, number = match.groups()
    node_type = {"D": "definition", "A": "axiom", "P": "proposition"}[kind]
    return f"{part}{kind}{number}", node_type


def node_page_href(node: dict) -> str:
    return f"/nodes/{node['code']}.html"


def node_code_parts(code: str) -> tuple[int, str, int]:
    match = re.match(r"^(IV|III|II|I|V)(D|A|P)(\d+)", code)
    if not match:
        return (99, "", 0)
    part, kind, number = match.groups()
    part_order = PART_ORDER.get(part, 99)
    return (part_order, kind, int(number))


def node_sort_key(node: dict) -> tuple[int, int, int, str]:
    part_order, kind, number = node_code_parts(node["code"])
    kind_order = {"D": 1, "A": 2, "P": 3}.get(kind, 9)
    return (part_order, kind_order, number, node["code"])


def node_peer_key(node: dict) -> tuple[int, str, str]:
    part_order, kind, _ = node_code_parts(node["code"])
    return (part_order, kind, node["type"])
