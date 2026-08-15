"""Canonical Ethics code parsing, classification and ordering."""

from __future__ import annotations

import pytest

from spinoza_ethics.codes import (
    classify_ethics_node,
    initial_part_for_file,
    node_code_parts,
    node_page_href,
    node_peer_key,
    node_sort_key,
    update_part_from_heading,
    visible_ethics_code,
)

# --- classify_ethics_node ------------------------------------------------


def test_classify_demonstration_from_leading_dem_label():
    assert classify_ethics_node("cite-IP11", "Dem.: If you deny this...") == "demonstration"


def test_classify_demonstration_from_embedded_dem_label():
    assert classify_ethics_node("cite-IP11", "P11: Dem.: If you deny this...") == "demonstration"


def test_classify_scholium():
    assert classify_ethics_node("cite-IP11", "Schol.: In this way...") == "scholium"


def test_classify_corollary():
    assert classify_ethics_node("cite-IP11", "Cor.: From this it follows...") == "corollary"


def test_classify_proposition_when_no_subpart_marker():
    assert classify_ethics_node("cite-IP11", "P11: God, or a substance...") == "proposition"


def test_classify_definition():
    assert classify_ethics_node("cite-ID1", "D1: By cause of itself I understand...") == "definition"


def test_classify_axiom():
    assert classify_ethics_node("cite-IA1", "A1: Whatever is, is either in itself...") == "axiom"


def test_classify_returns_empty_for_non_cite_anchor():
    """Anchors that are not ``cite-`` ids are not Ethics nodes at all."""
    assert classify_ethics_node("page-42", "P11: God, or a substance...") == ""


def test_classify_returns_empty_for_empty_anchor_id():
    assert classify_ethics_node("", "P11: anything") == ""


# --- initial_part_for_file / update_part_from_heading --------------------


@pytest.mark.parametrize(
    "rel,expected",
    [
        ("text/part0029_split_001.html", "I"),
        ("text/part0030.html", "II"),
        ("text/part0031.html", "III"),
        ("text/part0032.html", "IV"),
    ],
)
def test_initial_part_for_ethics_files(rel, expected):
    assert initial_part_for_file(rel) == expected


def test_initial_part_for_unknown_file_is_empty():
    assert initial_part_for_file("text/part0086.html") == ""


@pytest.mark.parametrize(
    "heading,expected",
    [
        ("FIRST PART OF THE ETHICS", "I"),
        ("Second Part of the Ethics", "II"),
        ("third part of the Ethics", "III"),
        ("Fourth Part of the Ethics", "IV"),
        ("Fifth Part of the Ethics", "V"),
    ],
)
def test_update_part_from_heading_recognises_each_part(heading, expected):
    assert update_part_from_heading(heading, "I") == expected


def test_update_part_from_heading_keeps_current_when_unrecognised():
    assert update_part_from_heading("Appendix", "III") == "III"


# --- visible_ethics_code -------------------------------------------------


def test_visible_code_strips_bracketed_page_prefix():
    text = "[5] D1: By cause of itself I understand that whose essence involves existence."
    assert visible_ethics_code(text, "I") == ("ID1", "definition")


def test_visible_code_strips_repeated_bracketed_prefixes():
    assert visible_ethics_code("[5] [II/45] A2: Man thinks.", "II") == ("IIA2", "axiom")


def test_visible_code_reads_proposition():
    assert visible_ethics_code("P11: God, or a substance...", "I") == ("IP11", "proposition")


def test_visible_code_without_a_part_is_empty():
    """Outside a numbered part there is no way to build a canonical code."""
    assert visible_ethics_code("P11: God, or a substance...", "") == ("", "")


def test_visible_code_ignores_unmatched_text():
    assert visible_ethics_code("Preface to the Ethics", "I") == ("", "")


def test_visible_code_requires_a_word_boundary_after_the_number():
    assert visible_ethics_code("P11a: not a code", "I") == ("", "")


# --- ordering ------------------------------------------------------------


def node(code: str, node_type: str = "proposition") -> dict:
    return {"code": code, "type": node_type}


def test_node_page_href():
    assert node_page_href(node("IIP7")) == "/nodes/IIP7.html"


def test_node_code_parts_splits_part_kind_number():
    assert node_code_parts("IVP18") == (4, "P", 18)


def test_node_code_parts_prefers_longest_part_numeral():
    assert node_code_parts("IIID2") == (3, "D", 2)


def test_node_code_parts_of_unparseable_code():
    assert node_code_parts("Appendix") == (99, "", 0)


def test_sort_puts_part_one_before_part_two():
    assert node_sort_key(node("IP1")) < node_sort_key(node("IIP1"))


def test_sort_puts_definitions_before_axioms_before_propositions():
    keys = [node_sort_key(node(c)) for c in ("ID1", "IA1", "IP1")]
    assert keys == sorted(keys)


def test_sort_is_numeric_not_lexicographic():
    """``P2`` must precede ``P10`` even though "IP10" < "IP2" as strings."""
    assert node_sort_key(node("IP2")) < node_sort_key(node("IP10"))


def test_sorted_nodes_are_in_canonical_order():
    codes = ["IIP1", "IP10", "IA1", "IP2", "ID1", "IP1"]
    ordered = [n["code"] for n in sorted((node(c) for c in codes), key=node_sort_key)]
    assert ordered == ["ID1", "IA1", "IP1", "IP2", "IP10", "IIP1"]


def test_peer_key_groups_same_part_kind_and_type():
    assert node_peer_key(node("IP1")) == node_peer_key(node("IP9"))


def test_peer_key_separates_different_node_types():
    assert node_peer_key(node("IP1", "proposition")) != node_peer_key(node("IP1", "scholium"))
