"""Thin helpers over ``xml.etree`` for reading and rewriting the source XHTML."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from .config import HTML_NS

ET.register_namespace("", HTML_NS)


def lname(tag: str) -> str:
    """Local name of a namespaced tag."""
    return tag.rsplit("}", 1)[-1]


def text_content(el: ET.Element) -> str:
    """Whitespace-collapsed text of an element and its descendants."""
    return re.sub(r"\s+", " ", "".join(el.itertext())).strip()


def parse(path: Path) -> ET.ElementTree:
    return ET.parse(path)


def node_to_html(el: ET.Element) -> str:
    return ET.tostring(el, encoding="unicode", method="html")


def absolutize_href(current_rel: str, href: str) -> str:
    """Rewrite a document-relative href to a site-absolute one.

    Fragment-only and already-absolute hrefs are returned untouched.
    """
    if not href or re.match(r"^[a-z]+:", href) or href.startswith("#"):
        return href
    if href.startswith("/"):
        return href
    base = Path(current_rel).parent
    if "#" in href:
        target, frag = href.split("#", 1)
        normalized = (base / target).as_posix()
        return f"/{normalized}#{frag}"
    normalized = (base / href).as_posix()
    return f"/{normalized}"


def graph_href(current_rel: str, href: str) -> str:
    """Site-absolute href used as a graph key.

    Unlike :func:`absolutize_href`, a bare fragment resolves against the
    current document so that it becomes a usable graph key.
    """
    if not href or re.match(r"^[a-z]+:", href):
        return href
    if href.startswith("#"):
        return f"/{current_rel}{href}"
    if href.startswith("/"):
        return href
    return absolutize_href(current_rel, href)
