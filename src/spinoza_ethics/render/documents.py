"""Rewrite each source document into a page that fits the site shell."""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from ..config import DOC_LABELS, HTML_NS, BuildConfig
from ..templating import site_url
from ..xmlutil import absolutize_href, lname, parse


def enhance_doc(config: BuildConfig, rel: str) -> str:
    """Return the site-shell version of one source document."""
    base = config.base_path

    tree = parse(config.source / rel)
    root = tree.getroot()
    head = root.find(".//{*}head")
    if head is None:
        head = ET.SubElement(root, "head")
    title = head.find("{*}title")
    if title is None:
        title = ET.SubElement(head, "title")
    title.text = f"{DOC_LABELS.get(rel, 'Spinoza')} | Spinoza Ethics Web"

    for child in list(head):
        if lname(child.tag) == "link":
            head.remove(child)
    link = ET.SubElement(head, "link")
    link.set("rel", "stylesheet")
    link.set("href", site_url(base, "/assets/site.css"))
    manifest = ET.SubElement(head, "link")
    manifest.set("rel", "manifest")
    manifest.set("href", site_url(base, "/manifest.webmanifest"))
    theme = ET.SubElement(head, "meta")
    theme.set("name", "theme-color")
    theme.set("content", "#fbfaf7")
    base_script = ET.SubElement(head, "script")
    base_script.text = f"window.SPINOZA_BASE_PATH = {json.dumps(base)};"
    script = ET.SubElement(head, "script")
    script.set("defer", "defer")
    script.set("src", site_url(base, "/assets/site-data.js"))
    script = ET.SubElement(head, "script")
    script.set("defer", "defer")
    script.set("src", site_url(base, "/assets/site-data-links.js"))
    script = ET.SubElement(head, "script")
    script.set("defer", "defer")
    script.set("src", site_url(base, "/assets/site-data-search.js"))
    script = ET.SubElement(head, "script")
    script.set("defer", "defer")
    script.set("src", site_url(base, "/assets/site.js"))
    script = ET.SubElement(head, "script")
    script.set("defer", "defer")
    script.set("src", site_url(base, "/assets/pwa.js"))

    body = root.find(".//{*}body")
    if body is not None:
        body.set("data-source-file", rel)
        original_children = list(body)
        for child in original_children:
            body.remove(child)
        shell = ET.Element("div", {"class": "reader-shell"})
        top = ET.Element("header", {"class": "topbar"})
        brand = ET.SubElement(top, "a", {"class": "brand", "href": site_url(base, "/index.html")})
        brand.text = "Spinoza Ethics"
        controls = ET.SubElement(top, "div", {"class": "top-actions"})
        search = ET.SubElement(controls, "input", {
            "id": "site-search",
            "type": "search",
            "placeholder": "Search Ethics, notes, glossary",
            "aria-label": "Search the site",
        })
        search.text = ""
        ET.SubElement(controls, "button", {"id": "toggle-apparatus", "type": "button"}).text = "References"

        main = ET.Element("main", {"class": "reader-main"})
        article = ET.SubElement(main, "article", {"class": "source-text"})
        banner = ET.SubElement(article, "nav", {"class": "doc-tools", "aria-label": "Document tools"})
        ET.SubElement(banner, "a", {"href": site_url(base, "/index.html#contents")}).text = "Contents"
        ET.SubElement(banner, "a", {"href": site_url(base, "/apparatus.html")}).text = "Apparatus"
        ET.SubElement(banner, "button", {"type": "button", "class": "copy-anchor"}).text = "Copy link"
        for child in original_children:
            article.append(child)

        aside = ET.SubElement(main, "aside", {"class": "apparatus-panel", "id": "apparatus-panel"})
        ET.SubElement(aside, "h2").text = "References"
        ET.SubElement(aside, "div", {"id": "selection-card", "class": "selection-card"}).text = "Select a link or section to inspect its target and backlinks."

        shell.append(top)
        shell.append(main)
        body.append(shell)

    for a in root.iter(f"{{{HTML_NS}}}a"):
        href = a.attrib.get("href")
        if href is not None:
            a.set("href", site_url(base, absolutize_href(rel, href)))
        classes = set(a.attrib.get("class", "").split())
        if "cite" in classes:
            classes.add("reference-link")
            a.set("data-ref-kind", "cite")
        if "gloss" in classes:
            classes.add("reference-link")
            a.set("data-ref-kind", "gloss")
        if a.attrib.get("{http://www.idpf.org/2007/ops}type") in {"noteref", "backlink"}:
            classes.add("reference-link")
        if classes:
            a.set("class", " ".join(sorted(classes)))

    for el in root.iter():
        src = el.attrib.get("src")
        if src and not re.match(r"^[a-z]+:", src) and not src.startswith("/"):
            el.set("src", site_url(base, "/" + (Path(rel).parent / src).as_posix()))

    return "<!doctype html>\n" + ET.tostring(root, encoding="unicode", method="html")


def write_documents(config: BuildConfig) -> None:
    """Write every source document into the output tree."""
    for rel in config.files:
        target = config.output / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(enhance_doc(config, rel), encoding="utf-8")
