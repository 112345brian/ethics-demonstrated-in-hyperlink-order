"""Href rewriting rules used to turn EPUB-relative links into site URLs."""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from spinoza_ethics.xmlutil import absolutize_href, graph_href, lname, text_content

CURRENT = "text/part0030.html"


def test_absolutize_sibling_relative_href():
    assert absolutize_href(CURRENT, "part0031.html") == "/text/part0031.html"


def test_absolutize_relative_href_with_fragment():
    assert absolutize_href(CURRENT, "part0031.html#cite-IIIP1") == "/text/part0031.html#cite-IIIP1"


def test_absolutize_leaves_bare_fragment_untouched():
    """A ``#foo`` link is already correct inside its own document."""
    assert absolutize_href(CURRENT, "#cite-IIP7") == "#cite-IIP7"


def test_absolutize_leaves_already_absolute_href_untouched():
    assert absolutize_href(CURRENT, "/nodes/IIP7.html") == "/nodes/IIP7.html"


@pytest.mark.parametrize("href", ["http://example.com/a", "https://example.com/a", "mailto:a@b.c"])
def test_absolutize_leaves_external_schemes_untouched(href):
    assert absolutize_href(CURRENT, href) == href


def test_absolutize_empty_href_is_empty():
    assert absolutize_href(CURRENT, "") == ""


def test_graph_href_resolves_bare_fragment_against_current_doc():
    """Unlike absolutize_href, graph keys must name the document."""
    assert graph_href(CURRENT, "#cite-IIP7") == "/text/part0030.html#cite-IIP7"


def test_graph_href_matches_absolutize_for_relative_hrefs():
    assert graph_href(CURRENT, "part0031.html#x") == absolutize_href(CURRENT, "part0031.html#x")


def test_graph_href_leaves_absolute_href_untouched():
    assert graph_href(CURRENT, "/text/part0031.html") == "/text/part0031.html"


@pytest.mark.parametrize("href", ["http://example.com/a", "mailto:a@b.c"])
def test_graph_href_leaves_external_schemes_untouched(href):
    assert graph_href(CURRENT, href) == href


def test_graph_href_empty_href_is_empty():
    assert graph_href(CURRENT, "") == ""


def test_lname_strips_namespace():
    assert lname("{http://www.w3.org/1999/xhtml}p") == "p"


def test_lname_passes_through_bare_tag():
    assert lname("p") == "p"


def test_text_content_collapses_whitespace_across_descendants():
    el = ET.fromstring("<p>P11:  God,\n or a\t<i>substance</i>  , exists.</p>")
    assert text_content(el) == "P11: God, or a substance , exists."
