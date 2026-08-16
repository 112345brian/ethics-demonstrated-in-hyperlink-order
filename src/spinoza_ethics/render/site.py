"""Top-level site pages: the workbench shell, the apparatus, the resource map."""

from __future__ import annotations

import html
import re

from ..codes import node_sort_key
from ..config import BuildConfig
from ..corpus import Corpus
from ..templating import render_page, site_url

#: The sidebar table of contents, in reading order. Ethics parts link to
#: their first canonical node rather than a source file: the EPUB splits
#: the text across files that don't line up with the work's own five-part
#: structure, so a file-per-card TOC produced misleading labels like
#: "Ethics I-II" and duplicated "Glossary-Index" cards for every page
#: split of the same section.
TOC_SECTIONS = [
    {"title": "Editorial Preface", "href": "/text/part0029_split_000.html"},
    {"title": "I. Of God", "part": "I"},
    {"title": "II. Of the Nature and Origin of the Mind", "part": "II"},
    {"title": "III. Of the Origin and Nature of the Affects", "part": "III"},
    {"title": "IV. Of Human Bondage, or of the Powers of the Affects", "part": "IV"},
    {"title": "V. Of the Power of the Intellect, or of Human Freedom", "part": "V"},
    {"title": "Curley Notes", "href": "/text/part0033.html"},
    {"title": "Glossary-Index", "href": "/text/part0034.html"},
    {"title": "Reference List", "href": "/text/part0039.html"},
    {"title": "Editorial Note", "href": "/text/part0086.html"},
]


def first_node_hrefs(corpus: Corpus) -> dict[str, str]:
    """The href of the first canonical node in each of the five Ethics parts."""
    hrefs: dict[str, str] = {}
    for node in sorted(corpus.ethics_nodes, key=node_sort_key):
        part = re.match(r"^(IV|III|II|I|V)", node["code"]).group(1)
        hrefs.setdefault(part, node["href"])
    return hrefs


#: Cards shown on the resources page.
RESOURCE_SECTIONS = [
    {
        "title": "Curley Notes to the Ethics",
        "href": "/text/part0033.html",
        "body": "Editorial and textual notes keyed from the Ethics text. Node dossiers pull directly from these anchors where a node links to a note.",
    },
    {
        "title": "Glossary-Index",
        "href": "/text/part0034.html",
        "body": "Curley’s term index and explanatory glossary. Node dossiers surface glossary entries linked from each proposition, definition, or axiom.",
    },
    {
        "title": "Reference List",
        "href": "/text/part0039.html",
        "body": "The edition’s bibliography, including Curley, Gueroult, Wolfson, Bennett, Joachim, Matheron, and other major resources cited in the notes and glossary.",
    },
    {
        "title": "Node Index",
        "href": "/nodes/index.html",
        "body": "Canonical index of all Ethics nodes with direct and transitive graph counts.",
    },
    {
        "title": "Graph Exports",
        "href": "/graph/ethics-graph.json",
        "body": "Machine-readable JSON plus CSV exports for nodes and edges.",
    },
    {
        "title": "Graph Model",
        "href": "/GRAPH_MODEL.md",
        "body": "Database schema, edge model, and example recursive dependency queries.",
    },
]


def write_index(config: BuildConfig, corpus: Corpus) -> None:
    """Write the workbench shell with its table of contents."""
    part_hrefs = first_node_hrefs(corpus)
    cards = []
    for section in TOC_SECTIONS:
        href = section["href"] if "href" in section else part_hrefs[section["part"]]
        section_href = html.escape(site_url(config.base_path, href))
        cards.append(
            f'<section class="toc-card"><h2><a href="{section_href}">{html.escape(section["title"])}</a></h2></section>'
        )
    page = render_page(config, "index.html", toc_cards="".join(cards))
    (config.output / "index.html").write_text(page, encoding="utf-8")


def write_apparatus(config: BuildConfig, corpus: Corpus) -> None:
    """Write the reference-apparatus overview page."""
    cite_count = sum(
        1 for refs in corpus.backlinks.values() for ref in refs if "cite" in ref.get("classes", "")
    )
    gloss_count = sum(
        1 for refs in corpus.backlinks.values() for ref in refs if "gloss" in ref.get("classes", "")
    )
    page = render_page(
        config,
        "apparatus.html",
        anchor_count=len(corpus.anchors),
        linked_targets=len([k for k, v in corpus.backlinks.items() if v]),
        cite_count=cite_count,
        gloss_count=gloss_count,
    )
    (config.output / "apparatus.html").write_text(page, encoding="utf-8")


def write_resources(config: BuildConfig) -> None:
    """Write the static map of the edition's study apparatus."""
    resources_dir = config.output / "resources"
    resources_dir.mkdir(parents=True, exist_ok=True)
    cards = "".join(
        f'<article class="resource-card"><h2><a href="{html.escape(site_url(config.base_path, item["href"]))}">'
        f'{html.escape(item["title"])}</a></h2>'
        f'<p>{html.escape(item["body"])}</p></article>'
        for item in RESOURCE_SECTIONS
    )
    page = render_page(config, "resources.html", cards=cards)
    (resources_dir / "index.html").write_text(page, encoding="utf-8")
