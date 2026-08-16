"""The sidebar table of contents: one card per Ethics part, not per source file."""

from __future__ import annotations

from spinoza_ethics.corpus import Corpus
from spinoza_ethics.render.site import TOC_SECTIONS, first_node_hrefs


def node(code: str, href: str) -> dict:
    return {"code": code, "href": href, "type": "definition", "label": code, "file": "x", "doc": "x"}


def test_first_node_hrefs_picks_the_earliest_node_per_part():
    corpus = Corpus(ethics_nodes=[
        node("ID2", "/text/a.html#cite-ID2"),
        node("ID1", "/text/a.html#cite-ID1"),
        node("IIP1", "/text/b.html#cite-IIP1"),
    ])
    hrefs = first_node_hrefs(corpus)
    assert hrefs["I"] == "/text/a.html#cite-ID1"
    assert hrefs["II"] == "/text/b.html#cite-IIP1"


def test_first_node_hrefs_only_has_entries_for_parts_present():
    corpus = Corpus(ethics_nodes=[node("ID1", "/text/a.html#cite-ID1")])
    assert first_node_hrefs(corpus) == {"I": "/text/a.html#cite-ID1"}


def test_first_node_hrefs_empty_corpus():
    assert first_node_hrefs(Corpus(ethics_nodes=[])) == {}


def test_toc_sections_cover_all_five_parts_exactly_once():
    parts = [s["part"] for s in TOC_SECTIONS if "part" in s]
    assert parts == ["I", "II", "III", "IV", "V"]


def test_toc_sections_every_entry_has_a_title_and_either_href_or_part():
    for section in TOC_SECTIONS:
        assert section["title"]
        assert ("href" in section) != ("part" in section)
