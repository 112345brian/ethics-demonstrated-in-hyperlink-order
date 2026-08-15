"""Top-level site pages: the workbench shell, the apparatus, the resource map."""

from __future__ import annotations

import html

from ..config import CORE_FILES, BuildConfig
from ..corpus import Corpus
from ..templating import render_page, site_url

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
    cards = []
    for rec in [r for r in corpus.records if r["file"] in CORE_FILES]:
        head_links = []
        for heading in rec["headings"][:12]:
            if heading["id"]:
                head_links.append(
                    f'<a href="{site_url(config.base_path, "/" + rec["file"])}#{html.escape(heading["id"])}">'
                    f'{html.escape(heading["text"][:90])}</a>'
                )
        section_href = html.escape(site_url(config.base_path, "/" + rec["file"]))
        cards.append(
            f'<section class="toc-card"><h2><a href="{section_href}">{html.escape(rec["title"])}</a></h2>'
            f'<div class="toc-links">{"".join(head_links)}</div></section>'
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
