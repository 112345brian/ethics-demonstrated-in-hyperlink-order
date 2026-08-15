from __future__ import annotations

import html
import csv
import json
import re
import shutil
import sqlite3
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote
import xml.etree.ElementTree as ET


SOURCE = Path("/tmp/spinoza_work").resolve()
OUT = Path("/Users/bri/epub-rebuilds-artifacts/spinoza-ethics-site").resolve()

CORE_FILES = [
    "text/part0029_split_000.html",  # Editorial Preface
    "text/part0029_split_001.html",  # Ethics I-II
    "text/part0030.html",            # Ethics II-III
    "text/part0031.html",            # Ethics III-IV
    "text/part0032.html",            # Ethics IV-V
    "text/part0033.html",            # Editorial Notes to Ethics
    "text/part0034.html",            # Glossary-Index preface / English-Latin-Dutch
    "text/part0035_split_000.html",
    "text/part0035_split_001.html",
    "text/part0036_split_000.html",
    "text/part0036_split_001.html",
    "text/part0037_split_000.html",
    "text/part0037_split_001.html",
    "text/part0037_split_002.html",
    "text/part0039.html",            # Reference List
    "text/part0086.html",            # Note on This EPUB
]

FILES = sorted(p.relative_to(SOURCE).as_posix() for p in (SOURCE / "text").glob("*.html"))
FILES.append("titlepage.xhtml")

DOC_LABELS = {
    "text/part0029_split_000.html": "Editorial Preface",
    "text/part0029_split_001.html": "Ethics I-II",
    "text/part0030.html": "Ethics II-III",
    "text/part0031.html": "Ethics III-IV",
    "text/part0032.html": "Ethics IV-V",
    "text/part0033.html": "Curley Notes",
    "text/part0034.html": "Glossary-Index",
    "text/part0035_split_000.html": "Glossary-Index",
    "text/part0035_split_001.html": "Latin-Dutch-English",
    "text/part0036_split_000.html": "Glossary-Index",
    "text/part0036_split_001.html": "Glossary-Index",
    "text/part0037_split_000.html": "Dutch-Latin-English",
    "text/part0037_split_001.html": "Dutch-Latin-English",
    "text/part0037_split_002.html": "Proper Names and Biblical References",
    "text/part0039.html": "Reference List",
    "text/part0086.html": "Editorial Note",
}

HTML_NS = "http://www.w3.org/1999/xhtml"
ET.register_namespace("", HTML_NS)


def lname(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def text_content(el: ET.Element) -> str:
    return re.sub(r"\s+", " ", "".join(el.itertext())).strip()


def parse(path: Path) -> ET.ElementTree:
    return ET.parse(path)


def node_to_html(el: ET.Element) -> str:
    return ET.tostring(el, encoding="unicode", method="html")


def absolutize_href(current_rel: str, href: str) -> str:
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
    if not href or re.match(r"^[a-z]+:", href):
        return href
    if href.startswith("#"):
        return f"/{current_rel}{href}"
    if href.startswith("/"):
        return href
    return absolutize_href(current_rel, href)


ETHICS_FILES = {
    "text/part0029_split_001.html",
    "text/part0030.html",
    "text/part0031.html",
    "text/part0032.html",
}


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


def collect_records() -> tuple[list[dict], dict[str, dict], dict[str, list[dict]], dict[str, list[dict]], list[dict], list[dict], dict[str, str]]:
    records: list[dict] = []
    anchors: dict[str, dict] = {}
    backlinks: dict[str, list[dict]] = defaultdict(list)
    outgoing: dict[str, list[dict]] = defaultdict(list)
    search: list[dict] = []
    ethics_nodes: list[dict] = []
    node_for_anchor: dict[str, str] = {}

    for rel in FILES:
        tree = parse(SOURCE / rel)
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
            if rel in ETHICS_FILES and lname(el.tag) == "a":
                if idv.startswith("cite-"):
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

    return records, anchors, backlinks, outgoing, search, ethics_nodes, node_for_anchor


def enhance_doc(rel: str, backlinks: dict[str, list[dict]]) -> str:
    tree = parse(SOURCE / rel)
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
    link.set("href", "/assets/site.css")
    script = ET.SubElement(head, "script")
    script.set("defer", "defer")
    script.set("src", "/assets/site-data.js")
    script = ET.SubElement(head, "script")
    script.set("defer", "defer")
    script.set("src", "/assets/site.js")

    body = root.find(".//{*}body")
    if body is not None:
        body.set("data-source-file", rel)
        original_children = list(body)
        for child in original_children:
            body.remove(child)
        shell = ET.Element("div", {"class": "reader-shell"})
        top = ET.Element("header", {"class": "topbar"})
        brand = ET.SubElement(top, "a", {"class": "brand", "href": "/index.html"})
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
        ET.SubElement(banner, "a", {"href": "/index.html#contents"}).text = "Contents"
        ET.SubElement(banner, "a", {"href": "/apparatus.html"}).text = "Apparatus"
        ET.SubElement(banner, "button", {"type": "button", "class": "copy-anchor"}).text = "Copy link"
        for child in original_children:
            article.append(child)

        aside = ET.SubElement(main, "aside", {"class": "apparatus-panel", "id": "apparatus-panel"})
        ET.SubElement(aside, "h2").text = "References"
        ET.SubElement(aside, "div", {"id": "selection-card", "class": "selection-card"}).text = "Select a link or section to inspect its target and backlinks."

        shell.append(top)
        shell.append(main)
        body.append(shell)

    for a in root.iter("{%s}a" % HTML_NS):
        href = a.attrib.get("href")
        if href is not None:
            a.set("href", absolutize_href(rel, href))
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
            el.set("src", "/" + (Path(rel).parent / src).as_posix())

    return "<!doctype html>\n" + ET.tostring(root, encoding="unicode", method="html")


def write_static(
    records: list[dict],
    anchors: dict[str, dict],
    backlinks: dict[str, list[dict]],
    outgoing: dict[str, list[dict]],
    search: list[dict],
    ethics_nodes: list[dict],
    node_for_anchor: dict[str, str],
) -> None:
    assets = OUT / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    (assets / "site-data.js").write_text(
        "window.SPINOZA_SITE_DATA = " + json.dumps({
            "records": records,
            "anchors": anchors,
            "backlinks": backlinks,
            "outgoing": outgoing,
            "search": search,
            "ethicsNodes": ethics_nodes,
            "nodeForAnchor": node_for_anchor,
            "coreFiles": CORE_FILES,
        }, ensure_ascii=False) + ";\n",
        encoding="utf-8",
    )
    (assets / "site.css").write_text(CSS, encoding="utf-8")
    (assets / "site.js").write_text(JS, encoding="utf-8")
    (assets / "app.js").write_text(APP_JS, encoding="utf-8")

    index_items = []
    for rec in [r for r in records if r["file"] in CORE_FILES]:
        head_links = []
        for h in rec["headings"][:12]:
            if h["id"]:
                head_links.append(f'<a href="/{rec["file"]}#{html.escape(h["id"])}">{html.escape(h["text"][:90])}</a>')
        index_items.append(
            f'<section class="toc-card"><h2><a href="/{rec["file"]}">{html.escape(rec["title"])}</a></h2>'
            f'<div class="toc-links">{"".join(head_links)}</div></section>'
        )

    index = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Spinoza Ethics Scholarly Workbench</title>
  <link rel="stylesheet" href="/assets/site.css">
  <script defer src="/assets/site-data.js"></script>
  <script defer src="/assets/app.js"></script>
</head>
<body class="app-body">
  <a class="skip-link" href="#app-document">Skip to text</a>
  <div class="app-frame">
    <header class="app-topbar">
      <a class="brand" href="/index.html">Spinoza Ethics</a>
      <div class="app-command">
        <input id="global-search" type="search" placeholder="Search Ethics, notes, glossary, references" aria-label="Search the corpus">
        <button id="toggle-columns" type="button" aria-pressed="false">Columns</button>
        <button id="toggle-marginalia" type="button" aria-pressed="true">Marginalia</button>
        <button id="open-apparatus" type="button">Apparatus</button>
      </div>
    </header>
    <aside class="app-sidebar" id="contents">
      <div class="sidebar-section">
        <p class="kicker">Focused corpus</p>
        <h1>Ethics Workbench</h1>
        <p>Ethics remains primary; referenced works are included as context.</p>
        <p><a href="/nodes/index.html">Node Index</a> · <a href="/resources/index.html">Resources</a> · <a href="/graph/ethics-graph.json">Graph JSON</a></p>
      </div>
      <nav id="app-toc" class="app-toc" aria-label="Ethics navigation">
        {''.join(index_items)}
      </nav>
      <section class="ethics-contents">
        <h2>Ethics Contents</h2>
        <div id="ethics-node-contents" class="ethics-node-contents"></div>
      </section>
    </aside>
    <main class="app-reader" id="app-reader" tabindex="-1">
      <nav id="wiki-breadcrumbs" class="wiki-breadcrumbs" aria-label="Breadcrumbs"></nav>
      <article id="app-document" class="source-text app-document"></article>
    </main>
    <aside class="app-panel" id="app-panel">
      <div class="panel-tabs" role="tablist" aria-label="Apparatus views">
        <button class="active" type="button" data-tab="target">Target</button>
        <button type="button" data-tab="context">Context</button>
        <button type="button" data-tab="dossier">Dossier</button>
        <button type="button" data-tab="proof">Proof Map</button>
        <button type="button" data-tab="chains">Chains</button>
        <button type="button" data-tab="matrix">Matrix</button>
        <button type="button" data-tab="graph">Graph</button>
        <button type="button" data-tab="incoming">Backlinks</button>
        <button type="button" data-tab="outgoing">Outgoing</button>
        <button type="button" data-tab="search">Search</button>
      </div>
      <section id="panel-content" class="panel-content">Loading apparatus...</section>
    </aside>
    <aside class="context-rail" id="context-rail" aria-label="Floating context"></aside>
  </div>
</body>
</html>
"""
    (OUT / "index.html").write_text(index, encoding="utf-8")

    cite_count = sum(1 for href, refs in backlinks.items() for ref in refs if "cite" in ref.get("classes", ""))
    gloss_count = sum(1 for href, refs in backlinks.items() for ref in refs if "gloss" in ref.get("classes", ""))
    linked_targets = len([k for k, v in backlinks.items() if v])
    apparatus = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Reference Apparatus | Spinoza Ethics</title>
  <link rel="stylesheet" href="/assets/site.css">
  <script defer src="/assets/site-data.js"></script>
  <script defer src="/assets/site.js"></script>
</head>
<body>
  <header class="topbar"><a class="brand" href="/index.html">Spinoza Ethics</a><div class="top-actions"><input id="site-search" type="search" placeholder="Search targets and references" aria-label="Search targets and references"></div></header>
  <main class="apparatus-page">
    <h1>Reference Apparatus</h1>
    <div class="stats"><span>{len(anchors)} anchors</span><span>{linked_targets} linked targets</span><span>{cite_count} citation links</span><span>{gloss_count} glossary links</span></div>
    <section id="apparatus-list" class="apparatus-list"></section>
  </main>
</body>
</html>
"""
    (OUT / "apparatus.html").write_text(apparatus, encoding="utf-8")
    write_node_pages(ethics_nodes, backlinks, outgoing, node_for_anchor)
    write_node_index_and_exports(ethics_nodes, backlinks, outgoing, node_for_anchor)
    write_resources_page()


def edge_type_for(edge: dict) -> str:
    classes = set((edge.get("classes") or "").split())
    target = edge.get("target", "")
    if "cite" in classes:
        return "cites"
    if "gloss" in classes:
        return "glosses"
    if "noteref" in classes:
        return "note-ref"
    if "backlink" in classes:
        return "backlink"
    if target.startswith("/text/"):
        return "links-to"
    return "external"


def node_page_href(node: dict) -> str:
    return f"/nodes/{node['code']}.html"


def node_code_parts(code: str) -> tuple[int, str, int]:
    match = re.match(r"^(IV|III|II|I|V)(D|A|P)(\d+)", code)
    if not match:
        return (99, "", 0)
    part, kind, number = match.groups()
    part_order = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5}.get(part, 99)
    return (part_order, kind, int(number))


def node_sort_key(node: dict) -> tuple[int, int, int, str]:
    part_order, kind, number = node_code_parts(node["code"])
    kind_order = {"D": 1, "A": 2, "P": 3}.get(kind, 9)
    return (part_order, kind_order, number, node["code"])


def node_peer_key(node: dict) -> tuple[int, str, str]:
    part_order, kind, _ = node_code_parts(node["code"])
    return (part_order, kind, node["type"])


def node_link_list(items: list[dict], empty_text: str) -> str:
    if not items:
        return f"<p>{html.escape(empty_text)}</p>"
    seen = set()
    rows = []
    for item in items:
        href = item.get("href") or item.get("from") or item.get("target") or "#"
        label = item.get("text") or item.get("label") or href
        doc = item.get("doc") or ""
        key = (href, label)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            f'<li><a href="{html.escape(href)}">{html.escape(label)}</a>'
            f'<span class="result-doc">{html.escape(doc)}</span></li>'
        )
    return f'<ul class="panel-list">{"".join(rows[:120])}</ul>'


def chain_link_list(items: list[dict], empty_text: str) -> str:
    if not items:
        return f"<p>{html.escape(empty_text)}</p>"
    rows = []
    for item in items[:160]:
        rows.append(
            f'<li style="--depth:{min(item.get("depth", 1), 8)}">'
            f'<a href="{html.escape(item["href"])}">{html.escape(item["text"])}</a>'
            f'<span class="result-doc">{html.escape("depth " + str(item.get("depth", 1)) + " · " + " -> ".join(item.get("path", [])))}</span></li>'
        )
    return f'<ol class="chain-list">{"".join(rows)}</ol>'


def render_node_source_html(node: dict) -> str:
    tree = parse(SOURCE / node["file"])
    root = tree.getroot()
    parents = {child: parent for parent in root.iter() for child in list(parent)}
    target = None
    for el in root.iter():
        if el.attrib.get("id") == node["id"]:
            target = el
            break
    if target is None:
        return f"<p>{html.escape(node['label'])}</p>"
    if lname(target.tag) == "a" and parents.get(target) is not None:
        target = parents[target]
    for el in target.iter():
        href = el.attrib.get("href")
        if href:
            el.set("href", absolutize_href(node["file"], href))
        src = el.attrib.get("src")
        if src and not re.match(r"^[a-z]+:", src) and not src.startswith("/"):
            el.set("src", "/" + (Path(node["file"]).parent / src).as_posix())
        classes = set(el.attrib.get("class", "").split())
        if "cite" in classes or "gloss" in classes:
            classes.add("reference-link")
            el.set("class", " ".join(sorted(classes)))
    return node_to_html(target)


def render_anchor_context_html(href: str) -> str:
    if not href.startswith("/"):
        return ""
    path, _, frag = href.removeprefix("/").partition("#")
    if not frag or not (SOURCE / path).exists():
        return ""
    tree = parse(SOURCE / path)
    root = tree.getroot()
    parents = {child: parent for parent in root.iter() for child in list(parent)}
    target = None
    for el in root.iter():
        if el.attrib.get("id") == frag:
            target = el
            break
    if target is None:
        return ""
    if lname(target.tag) == "a" and parents.get(target) is not None:
        target = parents[target]
    elif lname(target.tag) not in {"p", "li", "blockquote", "section"} and parents.get(target) is not None:
        target = parents[target]
    parent = parents.get(target)
    siblings = list(parent) if parent is not None else []
    bundle = [target]
    if target.attrib.get("class", "").startswith(("indexg", "indexmain")) and target in siblings:
        start = siblings.index(target) + 1
        for sibling in siblings[start:start + 3]:
            cls = sibling.attrib.get("class", "")
            if cls.startswith(("indexg", "indexmain")):
                break
            if lname(sibling.tag) == "p":
                bundle.append(sibling)
    for el in target.iter():
        link = el.attrib.get("href")
        if link:
            el.set("href", absolutize_href(path, link))
        classes = set(el.attrib.get("class", "").split())
        if "cite" in classes or "gloss" in classes:
            classes.add("reference-link")
            el.set("class", " ".join(sorted(classes)))
    for extra in bundle[1:]:
        for el in extra.iter():
            link = el.attrib.get("href")
            if link:
                el.set("href", absolutize_href(path, link))
            classes = set(el.attrib.get("class", "").split())
            if "cite" in classes or "gloss" in classes:
                classes.add("reference-link")
                el.set("class", " ".join(sorted(classes)))
    return "".join(node_to_html(el) for el in bundle)


def resource_cards(items: list[dict], empty_text: str) -> str:
    if not items:
        return f"<p>{html.escape(empty_text)}</p>"
    cards = []
    seen = set()
    for item in items[:40]:
        href = item["href"]
        if href in seen:
            continue
        seen.add(href)
        body = render_anchor_context_html(href)
        if not body:
            body = f'<p>{html.escape(item.get("label") or href)}</p>'
        cards.append(
            f'<article class="resource-card"><h3><a href="{html.escape(href)}">{html.escape(item["title"])}</a></h3>'
            f'<div class="resource-body">{body}</div></article>'
        )
    return f'<div class="resource-list">{"".join(cards)}</div>'


def write_node_pages(
    ethics_nodes: list[dict],
    backlinks: dict[str, list[dict]],
    outgoing: dict[str, list[dict]],
    node_for_anchor: dict[str, str],
) -> None:
    nodes_dir = OUT / "nodes"
    nodes_dir.mkdir(parents=True, exist_ok=True)
    by_href = {node["href"]: node for node in ethics_nodes}
    ordered = sorted(ethics_nodes, key=node_sort_key)
    peers_by_key: dict[tuple[int, str, str], list[dict]] = defaultdict(list)
    for peer in ordered:
        peers_by_key[node_peer_key(peer)].append(peer)

    def canonical(href: str) -> str:
        return node_for_anchor.get(href, href)

    def direct_items(node_href: str, direction: str) -> list[dict]:
        edges = outgoing.get(node_href, []) if direction == "out" else backlinks.get(node_href, [])
        items = []
        seen = set()
        for edge in edges:
            ref = canonical(edge.get("target" if direction == "out" else "from", ""))
            target_node = by_href.get(ref)
            if not target_node or ref in seen:
                continue
            seen.add(ref)
            items.append({
                "href": node_page_href(target_node),
                "node_href": ref,
                "code": target_node["code"],
                "text": f"{target_node['code']} · {target_node['type']}",
                "doc": target_node["label"],
            })
        return items

    def transitive_items(start_href: str, direction: str, max_depth: int = 8) -> list[dict]:
        queue = [(start_href, 0, [])]
        seen = {start_href}
        rows = []
        while queue:
            current, depth, path = queue.pop(0)
            if depth >= max_depth:
                continue
            for item in direct_items(current, direction):
                ref = item["node_href"]
                if ref in seen:
                    continue
                seen.add(ref)
                next_path = path + [item["code"]]
                row = dict(item)
                row["depth"] = depth + 1
                row["path"] = next_path
                rows.append(row)
                queue.append((ref, depth + 1, next_path))
        return rows

    def matrix_html(current_node: dict, deps: list[dict], uses: list[dict]) -> str:
        rows = deps[:28]
        cols = [{
            "href": node_page_href(current_node),
            "node_href": current_node["href"],
            "code": current_node["code"],
        }] + uses[:10]
        dep_sets = {col["node_href"]: {item["node_href"] for item in direct_items(col["node_href"], "out")} for col in cols}
        head = "".join(f'<th><a href="{html.escape(col["href"])}">{html.escape(col["code"])}</a></th>' for col in cols)
        body = []
        for row in rows:
            cells = "".join(
                f'<td class="{"has-edge" if row["node_href"] in dep_sets[col["node_href"]] else ""}">'
                f'{"use" if row["node_href"] in dep_sets[col["node_href"]] else ""}</td>'
                for col in cols
            )
            body.append(f'<tr><th><a href="{html.escape(row["href"])}">{html.escape(row["code"])}</a></th>{cells}</tr>')
        return f'<div class="matrix-scroll"><table class="usage-matrix"><thead><tr><th>Dependency</th>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'

    def graph_html(current_node: dict, deps: list[dict], uses: list[dict]) -> str:
        left = deps[:10]
        right = uses[:10]
        height = max(210, 84 + max(len(left), len(right)) * 34)
        center_y = height // 2
        lines = []
        nodes = []
        for index, item in enumerate(left):
            y = 42 + index * 34
            lines.append(f'<line x1="144" y1="{y}" x2="220" y2="{center_y}" />')
            nodes.append(f'<a href="{html.escape(item["href"])}"><circle cx="90" cy="{y}" r="18" class="dep-node"/><text x="90" y="{y + 4}" text-anchor="middle">{html.escape(item["code"])}</text></a>')
        for index, item in enumerate(right):
            y = 42 + index * 34
            lines.append(f'<line x1="240" y1="{center_y}" x2="316" y2="{y}" />')
            nodes.append(f'<a href="{html.escape(item["href"])}"><circle cx="370" cy="{y}" r="18" class="use-node"/><text x="370" y="{y + 4}" text-anchor="middle">{html.escape(item["code"])}</text></a>')
        focus = f'<circle cx="230" cy="{center_y}" r="26" class="focus-node"/><text x="230" y="{center_y + 5}" text-anchor="middle">{html.escape(current_node["code"])}</text>'
        return f'<svg class="node-graph" viewBox="0 0 460 {height}" role="img" aria-label="Node dependency graph">{"".join(lines)}{"".join(nodes)}{focus}</svg>'

    def dossier_items(node_href: str) -> tuple[list[dict], list[dict], list[dict]]:
        notes: list[dict] = []
        glossary: list[dict] = []
        resources: list[dict] = []
        for edge in outgoing.get(node_href, []):
            target = edge.get("target", "")
            if canonical(target) in by_href:
                continue
            kind = edge_type_for(edge)
            item = {
                "href": target,
                "title": edge.get("label") or target,
                "label": edge.get("label") or target,
            }
            if "part0033.html" in target or kind == "note-ref":
                item["title"] = f"Note {item['title']}"
                notes.append(item)
            elif kind == "glosses":
                item["title"] = f"Glossary: {item['title']}"
                glossary.append(item)
            elif target.startswith("/text/"):
                resources.append(item)
        return notes, glossary, resources

    for index, node in enumerate(ordered):
        href = node["href"]
        source_html = render_node_source_html(node)
        deps = direct_items(href, "out")
        uses = direct_items(href, "in")
        ancestors = transitive_items(href, "out")
        descendants = transitive_items(href, "in")
        notes, glossary, resources = dossier_items(href)
        peers = peers_by_key[node_peer_key(node)]
        peer_index = next((i for i, peer in enumerate(peers) if peer["href"] == href), -1)
        previous_node = peers[peer_index - 1] if peer_index > 0 else None
        next_node = peers[peer_index + 1] if peer_index >= 0 and peer_index + 1 < len(peers) else None
        prev_link = f'<a href="{node_page_href(previous_node)}">Previous: {html.escape(previous_node["code"])}</a>' if previous_node else ""
        next_link = f'<a href="{node_page_href(next_node)}">Next: {html.escape(next_node["code"])}</a>' if next_node else ""
        page = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(node["code"])} | Spinoza Ethics Node</title>
  <link rel="stylesheet" href="/assets/site.css">
  <script defer src="/assets/site-data.js"></script>
  <script defer src="/assets/site.js"></script>
</head>
<body>
  <a class="skip-link" href="#node-main">Skip to text</a>
  <header class="topbar"><a class="brand" href="/index.html">Spinoza Ethics</a><div class="top-actions"><a href="{html.escape(node["href"])}">Open in source</a><a href="/index.html?doc={quote(node["href"], safe="")}">Open in workbench</a></div></header>
  <main class="node-page">
    <nav class="wiki-breadcrumbs" aria-label="Breadcrumbs"><a href="/index.html">Ethics</a><span class="crumb-sep">/</span><a href="{html.escape(node["href"])}">{html.escape(node["doc"])}</a><span class="crumb-sep">/</span><a class="crumb-current" href="{node_page_href(node)}">{html.escape(node["code"])}</a></nav>
    <article class="node-main" id="node-main">
      <p class="kicker">{html.escape(node["type"])}</p>
      <h1>{html.escape(node["code"])}</h1>
      <section class="node-source source-text">
        {source_html}
      </section>
      <section class="commentary-shell">
        <h2>Commentary</h2>
        <p>This dossier gathers the available apparatus for {html.escape(node["code"])}: Curley notes, glossary entries, dependencies, descendants, graph data, and source links. Original interpretive commentary can be added here without disturbing the source text.</p>
      </section>
    </article>
    <aside class="node-apparatus">
      <section>
        <h2>Study Dossier</h2>
        <div class="stats"><span>{len(notes)} notes</span><span>{len(glossary)} glossary terms</span><span>{len(resources)} resources</span></div>
      </section>
      <section>
        <h2>Curley / Editorial Notes</h2>
        {resource_cards(notes, "No linked editorial notes recorded for this node.")}
      </section>
      <section>
        <h2>Glossary Terms</h2>
        {resource_cards(glossary, "No linked glossary terms recorded for this node.")}
      </section>
      <section>
        <h2>Other Linked Resources</h2>
        {resource_cards(resources, "No other linked resources recorded for this node.")}
      </section>
      <section>
        <h2>Trail</h2>
        <div class="trail-row">{prev_link}{next_link}</div>
      </section>
      <section>
        <h2>Uses</h2>
        {node_link_list(deps, "No explicit dependencies recorded for this node.")}
      </section>
      <section>
        <h2>Used By</h2>
        {node_link_list(uses, "No recorded uses of this node.")}
      </section>
      <section>
        <h2>All Ancestors</h2>
        {chain_link_list(ancestors, "No transitive ancestors recorded.")}
      </section>
      <section>
        <h2>All Descendants</h2>
        {chain_link_list(descendants, "No transitive descendants recorded.")}
      </section>
      <section>
        <h2>Usage Matrix</h2>
        {matrix_html(node, deps, uses)}
      </section>
      <section>
        <h2>Graph</h2>
        {graph_html(node, deps, uses)}
      </section>
    </aside>
  </main>
</body>
</html>
"""
        (nodes_dir / f"{node['code']}.html").write_text(page, encoding="utf-8")


def write_node_index_and_exports(
    ethics_nodes: list[dict],
    backlinks: dict[str, list[dict]],
    outgoing: dict[str, list[dict]],
    node_for_anchor: dict[str, str],
) -> None:
    nodes_dir = OUT / "nodes"
    graph_dir = OUT / "graph"
    nodes_dir.mkdir(parents=True, exist_ok=True)
    graph_dir.mkdir(parents=True, exist_ok=True)
    by_href = {node["href"]: node for node in ethics_nodes}
    ordered = sorted(ethics_nodes, key=node_sort_key)

    def canonical(href: str) -> str:
        return node_for_anchor.get(href, href)

    def direct_hrefs(node_href: str, direction: str) -> list[str]:
        edges = outgoing.get(node_href, []) if direction == "out" else backlinks.get(node_href, [])
        seen: set[str] = set()
        result: list[str] = []
        for edge in edges:
            ref = canonical(edge.get("target" if direction == "out" else "from", ""))
            if ref in by_href and ref not in seen:
                seen.add(ref)
                result.append(ref)
        return result

    def transitive_hrefs(start_href: str, direction: str, max_depth: int = 8) -> set[str]:
        queue = [(start_href, 0)]
        seen = {start_href}
        result: set[str] = set()
        while queue:
            current, depth = queue.pop(0)
            if depth >= max_depth:
                continue
            for ref in direct_hrefs(current, direction):
                if ref in seen:
                    continue
                seen.add(ref)
                result.add(ref)
                queue.append((ref, depth + 1))
        return result

    stats = []
    for node in ordered:
        deps = direct_hrefs(node["href"], "out")
        uses = direct_hrefs(node["href"], "in")
        ancestors = transitive_hrefs(node["href"], "out")
        descendants = transitive_hrefs(node["href"], "in")
        part_order, kind, _ = node_code_parts(node["code"])
        part_label = {1: "Part I", 2: "Part II", 3: "Part III", 4: "Part IV", 5: "Part V"}.get(part_order, "Other")
        stats.append({
            "code": node["code"],
            "type": node["type"],
            "part": part_label,
            "href": node_page_href(node),
            "source": node["href"],
            "label": node["label"],
            "direct_uses": len(deps),
            "direct_used_by": len(uses),
            "ancestors": len(ancestors),
            "descendants": len(descendants),
        })

    with (graph_dir / "ethics-nodes.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(stats[0].keys()))
        writer.writeheader()
        writer.writerows(stats)

    edge_rows = []
    seen_edges = set()
    for source, edges in outgoing.items():
        source_node = by_href.get(canonical(source))
        if not source_node:
            continue
        for edge in edges:
            target_node = by_href.get(canonical(edge.get("target", "")))
            if not target_node:
                continue
            row = {
                "source": source_node["code"],
                "source_href": node_page_href(source_node),
                "target": target_node["code"],
                "target_href": node_page_href(target_node),
                "type": edge_type_for(edge),
                "label": edge.get("label", ""),
                "via": edge.get("via", ""),
            }
            key = tuple(row.items())
            if key in seen_edges:
                continue
            seen_edges.add(key)
            edge_rows.append(row)

    with (graph_dir / "ethics-edges.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["source", "source_href", "target", "target_href", "type", "label", "via"])
        writer.writeheader()
        writer.writerows(edge_rows)

    (graph_dir / "ethics-graph.json").write_text(
        json.dumps({"nodes": stats, "edges": edge_rows}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    rows = []
    for row in stats:
        rows.append(
            f'<tr data-search="{html.escape((row["code"] + " " + row["type"] + " " + row["part"] + " " + row["label"]).lower())}">'
            f'<td><a href="{html.escape(row["href"])}">{html.escape(row["code"])}</a></td>'
            f'<td>{html.escape(row["type"])}</td><td>{html.escape(row["part"])}</td>'
            f'<td>{row["direct_uses"]}</td><td>{row["direct_used_by"]}</td>'
            f'<td>{row["ancestors"]}</td><td>{row["descendants"]}</td>'
            f'<td>{html.escape(row["label"])}</td></tr>'
        )

    index = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Ethics Node Index | Spinoza Ethics</title>
  <link rel="stylesheet" href="/assets/site.css">
</head>
<body>
  <a class="skip-link" href="#node-index-main">Skip to index</a>
  <header class="topbar"><a class="brand" href="/index.html">Spinoza Ethics</a><div class="top-actions"><a href="/graph/ethics-graph.json">Graph JSON</a><a href="/graph/ethics-nodes.csv">Nodes CSV</a><a href="/graph/ethics-edges.csv">Edges CSV</a></div></header>
  <main class="node-index-page" id="node-index-main">
    <p class="kicker">Canonical node pages</p>
    <h1>Ethics Node Index</h1>
    <div class="stats"><span>{len(stats)} nodes</span><span>{len(edge_rows)} graph edges</span><span>direct + transitive counts</span></div>
    <input id="node-index-filter" type="search" placeholder="Filter by code, type, part, or text" aria-label="Filter node index">
    <div class="matrix-scroll node-index-table">
      <table class="usage-matrix">
        <thead><tr><th>Node</th><th>Type</th><th>Part</th><th>Uses</th><th>Used By</th><th>Ancestors</th><th>Descendants</th><th>Text</th></tr></thead>
        <tbody id="node-index-body">{"".join(rows)}</tbody>
      </table>
    </div>
  </main>
  <script>
    const filter = document.getElementById('node-index-filter');
    const rows = Array.from(document.querySelectorAll('#node-index-body tr'));
    filter.addEventListener('input', () => {{
      const q = filter.value.trim().toLowerCase();
      rows.forEach(row => row.hidden = q && !row.dataset.search.includes(q));
    }});
  </script>
</body>
</html>
"""
    (nodes_dir / "index.html").write_text(index, encoding="utf-8")


def write_resources_page() -> None:
    resources_dir = OUT / "resources"
    resources_dir.mkdir(parents=True, exist_ok=True)
    sections = [
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
    cards = "".join(
        f'<article class="resource-card"><h2><a href="{item["href"]}">{html.escape(item["title"])}</a></h2><p>{html.escape(item["body"])}</p></article>'
        for item in sections
    )
    page = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Resources | Spinoza Ethics</title>
  <link rel="stylesheet" href="/assets/site.css">
</head>
<body>
  <a class="skip-link" href="#resources-main">Skip to resources</a>
  <header class="topbar"><a class="brand" href="/index.html">Spinoza Ethics</a><div class="top-actions"><a href="/nodes/index.html">Node Index</a><a href="/graph/ethics-graph.json">Graph JSON</a></div></header>
  <main class="node-index-page" id="resources-main">
    <p class="kicker">Study apparatus</p>
    <h1>Resources</h1>
    <p class="lede">A map of the edition’s built-in resources for understanding the Ethics: notes, glossary, bibliography, graph data, node dossiers, and the dependency model.</p>
    <div class="resource-list">{cards}</div>
  </main>
</body>
</html>
"""
    (resources_dir / "index.html").write_text(page, encoding="utf-8")


def write_graph_db(
    records: list[dict],
    anchors: dict[str, dict],
    backlinks: dict[str, list[dict]],
    outgoing: dict[str, list[dict]],
    search: list[dict],
    ethics_nodes: list[dict],
    node_for_anchor: dict[str, str],
) -> None:
    db_path = OUT / "spinoza-ethics.db"
    if db_path.exists():
        db_path.unlink()
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.executescript(
        """
        PRAGMA journal_mode = DELETE;
        CREATE TABLE document (
          file TEXT PRIMARY KEY,
          title TEXT NOT NULL,
          is_core INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE node (
          href TEXT PRIMARY KEY,
          code TEXT,
          type TEXT NOT NULL,
          label TEXT NOT NULL,
          file TEXT NOT NULL,
          doc TEXT NOT NULL,
          is_ethics INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE anchor (
          href TEXT PRIMARY KEY,
          file TEXT NOT NULL,
          local_id TEXT NOT NULL,
          kind TEXT,
          label TEXT,
          node_href TEXT,
          FOREIGN KEY(node_href) REFERENCES node(href)
        );
        CREATE TABLE edge (
          id INTEGER PRIMARY KEY,
          source TEXT NOT NULL,
          target TEXT NOT NULL,
          type TEXT NOT NULL,
          label TEXT,
          file TEXT,
          doc TEXT,
          via TEXT,
          FOREIGN KEY(source) REFERENCES node(href),
          FOREIGN KEY(target) REFERENCES node(href)
        );
        CREATE INDEX edge_source_idx ON edge(source, type);
        CREATE INDEX edge_target_idx ON edge(target, type);
        CREATE INDEX node_code_idx ON node(code);
        CREATE INDEX node_type_idx ON node(type);
        CREATE VIEW edge_unique AS
          SELECT source, target, type, min(label) AS label, min(file) AS file,
                 min(doc) AS doc, count(*) AS evidence_count
          FROM edge
          GROUP BY source, target, type;
        CREATE VIRTUAL TABLE search_fts USING fts5(href UNINDEXED, doc, text);
        """
    )
    for rec in records:
        cur.execute(
            "INSERT OR REPLACE INTO document(file,title,is_core) VALUES(?,?,?)",
            (rec["file"], rec["title"], 1 if rec["file"] in CORE_FILES else 0),
        )
    ethics_by_href = {n["href"]: n for n in ethics_nodes}
    for href, rec in anchors.items():
        node_href = node_for_anchor.get(href)
        if href in ethics_by_href:
            node_href = href
        cur.execute(
            "INSERT OR REPLACE INTO anchor(href,file,local_id,kind,label,node_href) VALUES(?,?,?,?,?,?)",
            (href, rec["file"], rec["id"], rec.get("kind"), rec.get("label"), node_href),
        )
    for href, rec in anchors.items():
        if href not in ethics_by_href and href not in node_for_anchor:
            cur.execute(
                "INSERT OR IGNORE INTO node(href,code,type,label,file,doc,is_ethics) VALUES(?,?,?,?,?,?,0)",
                (href, rec["id"], rec.get("kind") or "anchor", rec.get("label") or rec["id"], rec["file"], rec["doc"]),
            )
    for node in ethics_nodes:
        cur.execute(
            "INSERT OR REPLACE INTO node(href,code,type,label,file,doc,is_ethics) VALUES(?,?,?,?,?,?,1)",
            (node["href"], node["code"], node["type"], node["label"], node["file"], node["doc"]),
        )
    for href, node_href in node_for_anchor.items():
        if node_href in ethics_by_href:
            cur.execute("UPDATE anchor SET node_href=? WHERE href=?", (node_href, href))
    seen_edges = set()
    for source, edges in outgoing.items():
        source_node = node_for_anchor.get(source, source)
        for edge in edges:
            target = edge["target"]
            target_node = node_for_anchor.get(target, target)
            kind = edge_type_for(edge)
            row = (source_node, target_node, kind, edge.get("label"), edge.get("file"), edge.get("doc"), edge.get("via"))
            if row in seen_edges:
                continue
            seen_edges.add(row)
            cur.execute(
                "INSERT INTO edge(source,target,type,label,file,doc,via) VALUES(?,?,?,?,?,?,?)",
                row,
            )
    for row in search:
        cur.execute(
            "INSERT INTO search_fts(href,doc,text) VALUES(?,?,?)",
            (row["href"], row["doc"], row["text"]),
        )
    con.commit()
    cur.execute("PRAGMA optimize")
    con.commit()
    con.close()


def write_graph_model_note() -> None:
    (OUT / "GRAPH_MODEL.md").write_text(
        """# Spinoza Ethics Graph Model

Checked 2026-08-15.

The website is backed by a derived graph database at `spinoza-ethics.db`.
The browser still consumes `assets/site-data.js`, but that file is now an export of the same node/edge logic.

## Why SQLite

SQLite recursive common table expressions support graph traversal with `WITH RECURSIVE`.
SQLite FTS5 provides local full-text search over the extracted text records.
Together they are enough for dependency chains and scholarly lookup without adding a server.

Sources checked:
- https://www.sqlite.org/lang_with.html
- https://www.sqlite.org/fts5.html
- https://www.w3.org/TR/annotation-model/

## Tables

- `document`: source XHTML files and whether they are part of the Ethics-focused core.
- `node`: addressable scholarly objects. Ethics definitions, axioms, propositions, etc. have `is_ethics = 1`.
- `anchor`: every local HTML anchor, mapped to the nearest canonical Ethics node when possible.
- `edge`: typed directed relationships.
- `search_fts`: full-text search records.

## Edge Types

- `cites`: a body reference from one node/anchor to another.
- `glosses`: a glossary reference.
- `note-ref`: note marker to note body.
- `backlink`: return link from notes.
- `links-to`: ordinary internal link.

## Core Queries

Direct dependencies of a node:

```sql
SELECT e.type, n.code, n.type, n.label, e.evidence_count
FROM edge_unique e
JOIN node n ON n.href = e.target
WHERE e.source = '/text/part0032.html#cite-IVP37'
ORDER BY e.type, n.code;
```

Direct uses of a node:

```sql
SELECT e.type, n.code, n.type, n.label, e.evidence_count
FROM edge_unique e
JOIN node n ON n.href = e.source
WHERE e.target = '/text/part0032.html#cite-IVP37'
ORDER BY n.code;
```

Transitive dependency chain:

```sql
WITH RECURSIVE dep(depth, source, target, path) AS (
  SELECT 1, source, target, source || ' -> ' || target
  FROM edge_unique
  WHERE source = '/text/part0032.html#cite-IVP37'
    AND type = 'cites'
  UNION
  SELECT dep.depth + 1, e.source, e.target, dep.path || ' -> ' || e.target
  FROM edge_unique e
  JOIN dep ON e.source = dep.target
  WHERE e.type = 'cites'
    AND dep.depth < 8
    AND instr(dep.path, e.target) = 0
)
SELECT depth, source, target, path FROM dep;
```

Full-text search:

```sql
SELECT href, doc, snippet(search_fts, 2, '[', ']', '...', 12)
FROM search_fts
WHERE search_fts MATCH 'substance NEAR cause'
LIMIT 25;
```
""",
        encoding="utf-8",
    )


CSS = r"""





:root {
  color-scheme: light;
  --paper: #fbfaf7;
  --ink: #202020;
  --muted: #6f6a61;
  --rule: #d9d2c5;
  --accent: #0f5f6a;
  --accent-2: #8a3f2b;
  --panel: #f0eee8;
  --mark: #fff1b8;
  font-family: Georgia, "Times New Roman", serif;
}
* { box-sizing: border-box; }
html { scroll-padding-top: 84px; }
body {
  margin: 0;
  background: var(--paper);
  color: var(--ink);
}
a { color: var(--accent); text-decoration-thickness: .08em; text-underline-offset: .18em; }
a:visited { color: #5d4f86; }
a:hover, a:focus { color: var(--accent-2); }
a:focus-visible,
button:focus-visible,
input:focus-visible {
  outline: 3px solid rgba(15,95,106,.35);
  outline-offset: 2px;
}
.skip-link {
  position: fixed;
  left: 12px;
  top: 12px;
  z-index: 100;
  transform: translateY(-150%);
  border: 2px solid var(--accent);
  border-radius: 6px;
  background: #fffefa;
  color: var(--ink);
  padding: 10px 12px;
  font: 700 14px/1 ui-sans-serif, system-ui, sans-serif;
  text-decoration: none;
}
.skip-link:focus {
  transform: translateY(0);
}
.topbar {
  position: sticky;
  top: 0;
  z-index: 20;
  display: flex;
  gap: 16px;
  align-items: center;
  justify-content: space-between;
  padding: 10px 18px;
  border-bottom: 1px solid var(--rule);
  background: rgba(251,250,247,.96);
  backdrop-filter: blur(8px);
}
.brand {
  color: var(--ink);
  font: 700 18px/1.1 ui-serif, Georgia, serif;
  text-decoration: none;
  white-space: nowrap;
}
.top-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
input[type="search"] {
  width: min(42vw, 420px);
  min-width: 210px;
  border: 1px solid var(--rule);
  background: #fffefa;
  color: var(--ink);
  border-radius: 6px;
  padding: 8px 10px;
  font: 14px/1.2 ui-sans-serif, system-ui, sans-serif;
}
button, .home-actions a, .doc-tools a, .doc-tools button {
  border: 1px solid var(--rule);
  background: #fffefa;
  color: var(--ink);
  border-radius: 6px;
  padding: 8px 10px;
  min-height: 40px;
  font: 600 13px/1 ui-sans-serif, system-ui, sans-serif;
  text-decoration: none;
  cursor: pointer;
  touch-action: manipulation;
}
button[aria-pressed="true"] {
  border-color: var(--accent);
  color: var(--accent);
  background: #eef8f8;
}
.reader-main {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(300px, 420px);
  gap: 24px;
  align-items: start;
  max-width: 1480px;
  margin: 0 auto;
  padding: 24px;
}
.source-text {
  max-width: 820px;
  margin: 0 auto;
  font-size: 19px;
  line-height: 1.62;
}
.source-text p,
.source-text li,
.source-text blockquote {
  position: relative;
}
.source-text p { margin: .7em 0; }
.source-text h1, .source-text h2, .source-text h3, .source-text h4 {
  line-height: 1.15;
  margin: 2em 0 .75em;
}
.source-text h2 { font-size: 30px; }
.source-text h3 { font-size: 24px; }
.doc-tools {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 22px;
  font-family: ui-sans-serif, system-ui, sans-serif;
}
.apparatus-panel {
  position: sticky;
  top: 72px;
  max-height: calc(100vh - 92px);
  overflow: auto;
  border-left: 1px solid var(--rule);
  padding-left: 20px;
  font-family: ui-sans-serif, system-ui, sans-serif;
}
.apparatus-panel h2 {
  font-size: 15px;
  text-transform: uppercase;
  letter-spacing: .08em;
  color: var(--muted);
}
.selection-card, .preview-card {
  border: 1px solid var(--rule);
  background: var(--panel);
  border-radius: 8px;
  padding: 12px;
  margin: 10px 0;
  font-size: 14px;
  line-height: 1.45;
}
.preview-card h3 {
  margin: 0 0 8px;
  font-size: 15px;
}
.preview-card ul {
  padding-left: 18px;
}
.reference-link {
  background: linear-gradient(transparent 58%, rgba(15,95,106,.16) 58%);
}
.reference-link[data-ref-kind="gloss"] {
  background: linear-gradient(transparent 58%, rgba(138,63,43,.16) 58%);
}
:target {
  outline: 2px solid rgba(15,95,106,.35);
  background: rgba(255,241,184,.45);
  scroll-margin-top: 90px;
}
.line-marker { display: none; }
.line-anchor { display: inline; }
[epub\:type~="pagebreak"], [role="doc-pagebreak"] {
  color: var(--muted);
  font: 11px/1 ui-sans-serif, system-ui, sans-serif;
}
[role="doc-pagebreak"]::after {
  content: attr(aria-label);
  margin: 0 .35em;
  color: var(--muted);
}
.home-header {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 24px;
  align-items: end;
  max-width: 1180px;
  margin: 0 auto;
  padding: 56px 24px 26px;
  border-bottom: 1px solid var(--rule);
}
.kicker {
  margin: 0 0 8px;
  color: var(--muted);
  font: 700 12px/1 ui-sans-serif, system-ui, sans-serif;
  letter-spacing: .12em;
  text-transform: uppercase;
}
.home-header h1 {
  margin: 0;
  font-size: clamp(42px, 6vw, 78px);
  line-height: .96;
}
.lede {
  max-width: 760px;
  color: #3a3833;
  font-size: 20px;
  line-height: 1.45;
}
.home-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}
.home-grid {
  max-width: 1180px;
  margin: 0 auto;
  padding: 24px;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 14px;
}
.toc-card {
  border-top: 1px solid var(--rule);
  padding: 14px 0;
}
.toc-card h2 {
  margin: 0 0 10px;
  font-size: 20px;
}
.toc-links {
  display: grid;
  gap: 5px;
  font: 14px/1.35 ui-sans-serif, system-ui, sans-serif;
}
.apparatus-page {
  max-width: 1120px;
  margin: 0 auto;
  padding: 28px 24px;
}
.stats {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin: 14px 0 24px;
  font-family: ui-sans-serif, system-ui, sans-serif;
}
.stats span {
  border: 1px solid var(--rule);
  border-radius: 999px;
  padding: 6px 10px;
  background: #fffefa;
}
.apparatus-list {
  display: grid;
  gap: 10px;
}
.apparatus-entry {
  border-top: 1px solid var(--rule);
  padding-top: 12px;
}
.apparatus-entry h2 {
  margin: 0 0 6px;
  font-size: 18px;
}
.node-page {
  display: grid;
  grid-template-columns: minmax(0, 820px) minmax(280px, 380px);
  gap: 32px;
  max-width: 1280px;
  margin: 0 auto;
  padding: 20px 24px 60px;
}
.node-index-page {
  max-width: 1280px;
  margin: 0 auto;
  padding: 30px 24px 70px;
}
.node-index-page h1 {
  margin: 0 0 14px;
  font-size: clamp(38px, 6vw, 72px);
  line-height: .95;
}
.node-index-page input[type="search"] {
  width: min(100%, 680px);
  margin: 0 0 16px;
}
.node-index-table {
  max-height: calc(100vh - 230px);
}
.node-page > .wiki-breadcrumbs {
  grid-column: 1 / -1;
}
.node-main h1 {
  margin: 0 0 18px;
  font-size: clamp(38px, 6vw, 72px);
  line-height: .95;
}
.node-source {
  max-width: none;
  border-top: 1px solid var(--rule);
  padding-top: 16px;
}
.commentary-shell {
  margin-top: 28px;
  border-top: 1px solid var(--rule);
  padding-top: 16px;
  font-family: ui-sans-serif, system-ui, sans-serif;
}
.commentary-shell h2 {
  margin: 0 0 8px;
  color: var(--muted);
  font-size: 13px;
  letter-spacing: .08em;
  text-transform: uppercase;
}
.node-apparatus {
  position: sticky;
  top: 74px;
  align-self: start;
  max-height: calc(100vh - 92px);
  overflow: auto;
  border-left: 1px solid var(--rule);
  padding-left: 20px;
  font-family: ui-sans-serif, system-ui, sans-serif;
}
.node-apparatus section + section {
  margin-top: 22px;
}
.node-apparatus h2 {
  margin: 0 0 10px;
  color: var(--muted);
  font-size: 13px;
  letter-spacing: .08em;
  text-transform: uppercase;
}
.resource-list {
  display: grid;
  gap: 12px;
}
.resource-card {
  border-top: 1px solid var(--rule);
  padding-top: 10px;
}
.resource-card h2,
.resource-card h3 {
  margin: 0 0 6px;
  font: 700 15px/1.25 Georgia, serif;
  letter-spacing: 0;
  text-transform: none;
  color: var(--ink);
}
.resource-body {
  max-height: 220px;
  overflow: auto;
  font: 13px/1.42 ui-sans-serif, system-ui, sans-serif;
}
.resource-body p {
  margin: .35em 0;
}
.search-hit {
  outline: 2px solid rgba(138,63,43,.25);
  background: rgba(255,241,184,.55);
}
.app-body {
  overflow: hidden;
}
.app-frame {
  height: 100vh;
  display: grid;
  grid-template-columns: 300px minmax(0, 1fr) 390px;
  grid-template-rows: auto minmax(0, 1fr);
  grid-template-areas:
    "top top top"
    "side reader panel";
}
.app-topbar {
  grid-area: top;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  border-bottom: 1px solid var(--rule);
  background: #fffefa;
  padding: 10px 14px;
}
.app-command {
  display: flex;
  gap: 8px;
  align-items: center;
  width: min(720px, 70vw);
  flex-wrap: wrap;
}
.app-command input {
  flex: 1 1 260px;
  min-width: 180px;
}
.app-sidebar {
  grid-area: side;
  overflow: auto;
  border-right: 1px solid var(--rule);
  background: #f6f3ed;
  padding: 16px;
}
.sidebar-section h1 {
  margin: 0 0 8px;
  font-size: 30px;
  line-height: 1;
}
.sidebar-section p:last-child {
  color: var(--muted);
  font: 14px/1.35 ui-sans-serif, system-ui, sans-serif;
}
.app-toc {
  display: grid;
  gap: 10px;
}
.app-toc .toc-card {
  padding: 10px 0;
}
.app-toc .toc-card h2 {
  font-size: 16px;
}
.ethics-contents {
  margin-top: 22px;
  border-top: 1px solid var(--rule);
  padding-top: 14px;
}
.ethics-contents h2 {
  margin: 0 0 10px;
  font: 700 14px/1 ui-sans-serif, system-ui, sans-serif;
  text-transform: uppercase;
  letter-spacing: .08em;
  color: var(--muted);
}
.ethics-node-contents {
  display: grid;
  gap: 10px;
}
.node-group {
  display: grid;
  gap: 4px;
}
.node-group h3 {
  margin: 8px 0 2px;
  color: var(--muted);
  font: 700 12px/1 ui-sans-serif, system-ui, sans-serif;
}
.node-group a {
  display: grid;
  grid-template-columns: 62px minmax(0, 1fr);
  gap: 8px;
  align-items: baseline;
  padding: 4px 0;
  color: var(--ink);
  text-decoration: none;
  font: 13px/1.25 ui-sans-serif, system-ui, sans-serif;
}
.node-group a:hover {
  color: var(--accent);
}
.node-code {
  color: var(--accent);
  font-weight: 700;
}
.node-label {
  color: var(--muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.app-reader {
  grid-area: reader;
  overflow: auto;
  padding: 0 24px 60px;
}
.app-document {
  padding-top: 24px;
}
.columns-on .app-document {
  max-width: 1120px;
  column-count: 2;
  column-gap: 42px;
  column-rule: 1px solid var(--rule);
}
.columns-on .app-document h1,
.columns-on .app-document h2 {
  column-span: all;
}
.columns-on .app-document h3,
.columns-on .app-document h4,
.columns-on .app-document p,
.columns-on .app-document li,
.columns-on .app-document blockquote {
  break-inside: avoid;
}
.margin-note {
  display: none;
}
.marginalia-on .app-document:not(.app-loading) {
  max-width: 1040px;
  padding-right: 210px;
}
.marginalia-on .margin-note {
  display: grid;
  gap: 4px;
  position: absolute;
  left: calc(100% + 18px);
  top: .2em;
  width: 180px;
  border-left: 2px solid rgba(15,95,106,.24);
  padding-left: 10px;
  color: var(--muted);
  font: 12px/1.25 ui-sans-serif, system-ui, sans-serif;
}
.marginalia-on .margin-note a {
  color: var(--muted);
  text-decoration: none;
}
.marginalia-on .margin-note a:hover {
  color: var(--accent);
  text-decoration: underline;
}
.columns-on.marginalia-on .app-document {
  padding-right: 0;
}
.columns-on.marginalia-on .margin-note {
  position: static;
  display: inline-grid;
  width: auto;
  max-width: 100%;
  margin: .45em 0 .2em;
  break-inside: avoid;
}
.wiki-breadcrumbs {
  position: sticky;
  top: 0;
  z-index: 12;
  display: flex;
  gap: 6px;
  align-items: center;
  flex-wrap: wrap;
  min-height: 44px;
  border-bottom: 1px solid var(--rule);
  background: rgba(251,250,247,.96);
  backdrop-filter: blur(8px);
  padding: 10px 0;
  font: 13px/1.2 ui-sans-serif, system-ui, sans-serif;
}
.wiki-breadcrumbs a,
.wiki-breadcrumbs span {
  color: var(--muted);
  text-decoration: none;
}
.wiki-breadcrumbs a:hover {
  color: var(--accent);
}
.wiki-breadcrumbs .crumb-current {
  color: var(--ink);
  font-weight: 700;
}
.wiki-breadcrumbs .crumb-sep {
  color: #aaa195;
}
.crumb-spacer {
  flex: 1 1 24px;
}
.crumb-trail {
  display: flex;
  gap: 6px;
  align-items: center;
  flex-wrap: wrap;
}
.trail-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(94px, 1fr));
  gap: 8px;
}
.trail-card {
  display: grid;
  gap: 2px;
  border: 1px solid var(--rule);
  border-radius: 6px;
  background: #fffefa;
  padding: 7px 8px;
  color: var(--ink);
  text-decoration: none;
  min-width: 0;
}
.crumb-trail .trail-card {
  grid-template-columns: auto auto;
  align-items: baseline;
  padding: 4px 7px;
}
.trail-card span {
  color: var(--muted);
  font: 700 10px/1 ui-sans-serif, system-ui, sans-serif;
  text-transform: uppercase;
}
.trail-card strong {
  color: var(--accent);
  font: 700 13px/1 ui-sans-serif, system-ui, sans-serif;
}
.trail-card em {
  color: var(--muted);
  font: 12px/1.1 ui-sans-serif, system-ui, sans-serif;
  font-style: normal;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.crumb-trail .trail-card em {
  display: none;
}
.context-rail {
  position: fixed;
  left: 0;
  top: 34vh;
  z-index: 35;
  display: flex;
  align-items: stretch;
  transform: translateX(calc(-100% + 34px));
  transition: transform .16s ease;
  font-family: ui-sans-serif, system-ui, sans-serif;
}
.context-rail:hover,
.context-rail:focus-within {
  transform: translateX(0);
}
.rail-handle {
  writing-mode: vertical-rl;
  text-orientation: mixed;
  border-radius: 0 6px 6px 0;
  background: var(--accent);
  color: #fffefa;
  border-color: var(--accent);
  padding: 10px 7px;
}
.rail-body {
  width: 238px;
  display: grid;
  gap: 8px;
  border: 1px solid var(--rule);
  border-left: 0;
  background: #fffefa;
  box-shadow: 0 12px 34px rgba(32,32,32,.14);
  padding: 10px;
}
.rail-body strong {
  font: 700 16px/1 Georgia, serif;
}
.rail-body > span {
  color: var(--muted);
  font-size: 12px;
}
.rail-counts {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
}
.rail-counts button {
  padding: 7px 6px;
  font-size: 12px;
}
.rail-jump {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
}
.rail-jump .trail-card {
  min-width: 0;
}
.app-panel {
  grid-area: panel;
  overflow: hidden;
  border-left: 1px solid var(--rule);
  background: #f6f3ed;
  display: flex;
  flex-direction: column;
}
.panel-tabs {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(64px, 1fr));
  gap: 0;
  border-bottom: 1px solid var(--rule);
}
.panel-tabs button {
  border: 0;
  border-right: 1px solid var(--rule);
  border-radius: 0;
  background: transparent;
  padding: 12px 6px;
}
.panel-tabs button.active {
  background: #fffefa;
  color: var(--accent);
}
.panel-content {
  overflow: auto;
  padding: 14px;
  font: 14px/1.45 ui-sans-serif, system-ui, sans-serif;
}
.panel-content h2 {
  font: 700 18px/1.2 Georgia, serif;
  margin: 0 0 8px;
}
.panel-content h3 {
  font-size: 13px;
  text-transform: uppercase;
  letter-spacing: .08em;
  color: var(--muted);
  margin: 18px 0 8px;
}
.panel-list {
  display: grid;
  gap: 8px;
  padding: 0;
  margin: 0;
  list-style: none;
}
.panel-list li {
  border-top: 1px solid var(--rule);
  padding-top: 8px;
}
.chain-list {
  display: grid;
  gap: 7px;
  margin: 0;
  padding: 0;
  list-style: none;
}
.chain-list li {
  border-top: 1px solid var(--rule);
  padding: 7px 0 0 calc(var(--depth, 1) * 10px);
}
.matrix-scroll {
  overflow: auto;
  border: 1px solid var(--rule);
  background: #fffefa;
}
.usage-matrix {
  width: 100%;
  min-width: 540px;
  border-collapse: collapse;
  font-size: 12px;
}
.usage-matrix th,
.usage-matrix td {
  border: 1px solid var(--rule);
  padding: 6px;
  text-align: center;
  vertical-align: top;
}
.usage-matrix th:first-child {
  position: sticky;
  left: 0;
  z-index: 1;
  background: #fffefa;
  text-align: left;
}
.usage-matrix .has-edge {
  background: rgba(15,95,106,.14);
  color: var(--accent);
  font-weight: 700;
}
.node-graph {
  width: 100%;
  min-height: 260px;
  border: 1px solid var(--rule);
  background: #fffefa;
}
.node-graph line {
  stroke: rgba(111,106,97,.45);
  stroke-width: 1.4;
}
.node-graph circle {
  stroke: var(--accent);
  stroke-width: 1.5;
}
.node-graph .focus-node {
  fill: var(--accent);
}
.node-graph .dep-node {
  fill: #eef8f8;
}
.node-graph .use-node {
  fill: #fff1e8;
  stroke: var(--accent-2);
}
.node-graph text {
  fill: var(--ink);
  font: 700 10px/1 ui-sans-serif, system-ui, sans-serif;
  pointer-events: none;
}
.node-graph .focus-node + text {
  fill: #fffefa;
}
.result-doc {
  display: block;
  color: var(--muted);
  font-size: 12px;
  margin-top: 2px;
}
.hover-card {
  position: fixed;
  z-index: 60;
  width: min(460px, calc(100vw - 28px));
  max-height: min(420px, calc(100vh - 28px));
  overflow: auto;
  border: 1px solid var(--rule);
  background: #fffefa;
  box-shadow: 0 18px 50px rgba(32,32,32,.18);
  border-radius: 8px;
  padding: 12px;
  font: 14px/1.45 ui-sans-serif, system-ui, sans-serif;
}
.hover-card h2 {
  margin: 0 0 5px;
  font: 700 17px/1.2 Georgia, serif;
}
.hover-card p {
  margin: 7px 0;
}
.hover-card .hover-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 9px;
}
.hover-card .hover-actions a,
.hover-card .hover-actions button {
  font-size: 12px;
}
.app-loading {
  color: var(--muted);
  font-family: ui-sans-serif, system-ui, sans-serif;
}
@media (max-width: 980px) {
  .reader-main { grid-template-columns: 1fr; padding: 18px; }
  .apparatus-panel { position: static; max-height: none; border-left: 0; border-top: 1px solid var(--rule); padding: 18px 0 0; }
  .home-header { grid-template-columns: 1fr; }
  .home-actions { justify-content: flex-start; }
  .node-page { grid-template-columns: 1fr; padding: 18px; }
  .node-apparatus { position: static; max-height: none; border-left: 0; border-top: 1px solid var(--rule); padding: 18px 0 0; }
  .resource-body { max-height: none; }
  .app-body { overflow: auto; }
  .app-frame {
    height: auto;
    min-height: 100vh;
    grid-template-columns: 1fr;
    grid-template-areas: "top" "reader" "panel" "side";
  }
  .app-topbar { align-items: flex-start; flex-wrap: wrap; }
  .app-command { width: 100%; }
  .app-command input { flex-basis: 100%; }
  .app-sidebar, .app-reader, .app-panel { overflow: visible; }
  .app-sidebar { border-right: 0; border-top: 1px solid var(--rule); }
  .app-reader { padding: 0 18px 36px; }
  .app-panel { min-height: 360px; }
  .panel-tabs {
    display: flex;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
  }
  .panel-tabs button {
    min-width: max-content;
    min-height: 44px;
    padding-inline: 12px;
    white-space: nowrap;
  }
  .context-rail { display: none; }
  .columns-on .app-document { column-count: 1; column-rule: 0; }
  .marginalia-on .app-document { padding-right: 0; }
  .marginalia-on .margin-note {
    position: static;
    display: grid;
    width: auto;
    margin: .45em 0 .2em;
  }
}
@media (max-width: 620px) {
  .topbar { align-items: stretch; flex-direction: column; }
  .top-actions { flex-wrap: wrap; }
  .top-actions a { min-height: 40px; display: inline-flex; align-items: center; }
  input[type="search"] { width: 100%; min-width: 0; }
  .source-text { font-size: 17px; }
  .app-topbar { padding: 10px; }
  .app-command button { flex: 1 1 44%; min-height: 44px; }
  .wiki-breadcrumbs { position: static; }
  .node-group a { min-height: 36px; }
  .usage-matrix th,
  .usage-matrix td { padding: 7px 8px; }
}
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    scroll-behavior: auto !important;
    transition-duration: .001ms !important;
    animation-duration: .001ms !important;
    animation-iteration-count: 1 !important;
  }
}

"""


JS = r"""
(function () {
  const data = window.SPINOZA_SITE_DATA || { anchors: {}, backlinks: {}, records: [] };
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  function samePathTarget(href) {
    try {
      const url = new URL(href, location.href);
      return url.origin === location.origin ? url.pathname + url.hash : null;
    } catch {
      return null;
    }
  }

  function snippetFor(target) {
    const id = target && target.split("#")[1];
    const el = id ? document.getElementById(id) : null;
    if (!el) return null;
    return el.textContent.replace(/\s+/g, " ").trim().slice(0, 520);
  }

  function renderCard(target, linkText) {
    const panel = $("#selection-card");
    if (!panel || !target) return;
    const rec = data.anchors[target] || {};
    const hereSnippet = snippetFor(target);
    const backs = data.backlinks[target] || [];
    const targetLink = `<a href="${target}">${escapeHtml(rec.label || linkText || target)}</a>`;
    const backItems = backs.slice(0, 12).map(b => `<li><a href="${b.from || '/' + b.file}">${escapeHtml(b.label || b.doc)}</a> <span>${escapeHtml(b.doc || "")}</span></li>`).join("");
    panel.innerHTML = `
      <div class="preview-card">
        <h3>${targetLink}</h3>
        <p>${escapeHtml(rec.doc || "Linked target")}</p>
        ${hereSnippet ? `<p>${escapeHtml(hereSnippet)}</p>` : ""}
        <p><button type="button" data-copy="${target}">Copy target link</button></p>
      </div>
      <div class="preview-card">
        <h3>Referenced by ${backs.length}</h3>
        ${backs.length ? `<ul>${backItems}</ul>` : `<p>No recorded backlinks in this build.</p>`}
      </div>
    `;
  }

  function escapeHtml(value) {
    return String(value || "").replace(/[&<>"']/g, ch => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
    }[ch]));
  }

  document.addEventListener("click", event => {
    const copy = event.target.closest("[data-copy], .copy-anchor");
    if (copy) {
      const target = copy.dataset.copy || (location.pathname + location.hash);
      navigator.clipboard && navigator.clipboard.writeText(location.origin + target);
      copy.textContent = "Copied";
      setTimeout(() => { copy.textContent = copy.classList.contains("copy-anchor") ? "Copy link" : "Copy target link"; }, 1200);
      return;
    }
    const a = event.target.closest("a[href]");
    if (!a) return;
    const target = samePathTarget(a.getAttribute("href"));
    if (target && (a.classList.contains("reference-link") || data.backlinks[target])) {
      renderCard(target, a.textContent.trim());
    }
  });

  document.addEventListener("mouseover", event => {
    const a = event.target.closest("a.reference-link[href]");
    if (!a) return;
    const target = samePathTarget(a.getAttribute("href"));
    if (target) renderCard(target, a.textContent.trim());
  });

  const toggle = $("#toggle-apparatus");
  if (toggle) {
    toggle.addEventListener("click", () => $("#apparatus-panel")?.scrollIntoView({ behavior: "smooth", block: "start" }));
  }

  const search = $("#site-search");
  if (search) {
    search.addEventListener("input", () => {
      $$(".search-hit").forEach(el => el.classList.remove("search-hit"));
      const q = search.value.trim().toLowerCase();
      if (!q) return;
      const hit = $$("p, h1, h2, h3, h4, li").find(el => el.textContent.toLowerCase().includes(q));
      if (hit) {
        hit.classList.add("search-hit");
        hit.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    });
  }

  const list = $("#apparatus-list");
  if (list) {
    const entries = Object.entries(data.backlinks)
      .filter(([, refs]) => refs.length)
      .sort((a, b) => b[1].length - a[1].length)
      .slice(0, 500);
    list.innerHTML = entries.map(([target, refs]) => {
      const rec = data.anchors[target] || {};
      const refsHtml = refs.slice(0, 10).map(r => `<li><a href="${r.from || '/' + r.file}">${escapeHtml(r.label || r.doc)}</a> <span>${escapeHtml(r.doc || "")}</span></li>`).join("");
      return `<article class="apparatus-entry"><h2><a href="${target}">${escapeHtml(rec.label || target)}</a></h2><p>${escapeHtml(rec.doc || "")} · ${refs.length} incoming reference${refs.length === 1 ? "" : "s"}</p><ul>${refsHtml}</ul></article>`;
    }).join("");
  }

  if (location.hash) {
    const target = location.pathname + location.hash;
    if (data.backlinks[target]) renderCard(target, "");
  }
})();
"""


APP_JS = r"""





(function () {
  const data = window.SPINOZA_SITE_DATA || { anchors: {}, backlinks: {}, outgoing: {}, search: [], records: [], coreFiles: [], ethicsNodes: [], nodeForAnchor: {} };
  const state = {
    currentPath: "/text/part0029_split_001.html",
    currentHash: "",
    selectedTarget: "",
    activeTab: "target",
    lastSearch: "",
    contextPinned: false,
    columns: localStorage.getItem("spinoza:columns") === "1",
    marginalia: localStorage.getItem("spinoza:marginalia") !== "0",
  };
  const docCache = new Map();
  let hoverTimer = 0;
  let hoverCard = null;
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  function escapeHtml(value) {
    return String(value || "").replace(/[&<>"']/g, ch => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
    }[ch]));
  }

  function normalizeHref(href, basePath = location.pathname) {
    try {
      const url = new URL(href, location.origin + basePath);
      if (url.origin !== location.origin) return href;
      return url.pathname + url.hash;
    } catch {
      return href || "";
    }
  }

  function splitTarget(target) {
    const [path, hash = ""] = target.split("#");
    return { path: path || state.currentPath, hash: hash ? "#" + hash : "" };
  }

  async function fetchDoc(path) {
    if (docCache.has(path)) return docCache.get(path);
    const response = await fetch(path, { cache: "force-cache" });
    const html = await response.text();
    const doc = new DOMParser().parseFromString(html, "text/html");
    docCache.set(path, doc);
    return doc;
  }

  async function loadDocument(target, push = true) {
    const parts = splitTarget(target);
    state.currentPath = parts.path || state.currentPath;
    state.currentHash = parts.hash || "";
    const reader = $("#app-document");
    if (!reader) return;
    reader.innerHTML = '<p class="app-loading">Loading source...</p>';
    const doc = await fetchDoc(state.currentPath);
    const article = doc.querySelector(".source-text") || doc.body;
    reader.innerHTML = article.innerHTML;
    reader.querySelectorAll("script, .topbar, .apparatus-panel, .doc-tools").forEach(el => el.remove());
    reader.querySelectorAll("a[href]").forEach(a => {
      a.href = normalizeHref(a.getAttribute("href"), state.currentPath);
      if (a.classList.contains("cite") || a.classList.contains("gloss")) {
        a.classList.add("reference-link");
      }
    });
    buildMarginalia(reader);
    applyReaderModes();
    if (push) {
      const appUrl = "/index.html?doc=" + encodeURIComponent(state.currentPath + state.currentHash);
      history.pushState({ target: state.currentPath + state.currentHash }, "", appUrl);
      localStorage.setItem("spinoza:lastTarget", state.currentPath + state.currentHash);
    }
    requestAnimationFrame(() => {
      if (state.currentHash) {
        const id = CSS.escape(state.currentHash.slice(1));
        const el = reader.querySelector("#" + id);
        if (el) el.scrollIntoView({ block: "start" });
      }
      selectTarget(state.currentPath + state.currentHash);
    });
  }

  async function targetSnippet(target) {
    const parts = splitTarget(target);
    const doc = await fetchDoc(parts.path);
    const id = parts.hash ? parts.hash.slice(1) : "";
    let el = id ? doc.getElementById(id) : doc.querySelector(".source-text");
    if (el && el.tagName === "A" && !el.textContent.trim()) el = el.parentElement || el;
    if (!el) return "";
    let text = el.textContent.replace(/\s+/g, " ").trim();
    if (text.length < 80 && el.parentElement) {
      text = el.parentElement.textContent.replace(/\s+/g, " ").trim();
    }
    return text.slice(0, 900);
  }

  function selectTarget(target) {
    state.selectedTarget = target || state.currentPath + state.currentHash;
    renderBreadcrumbs(state.selectedTarget);
    renderContextRail(state.selectedTarget);
    renderPanel();
  }

  function currentSectionHref() {
    const visible = $$("#app-document [id]").find(el => {
      const rect = el.getBoundingClientRect();
      return rect.top >= 70 && rect.top < window.innerHeight * 0.58;
    });
    return state.currentPath + (visible ? "#" + visible.id : state.currentHash);
  }

  function linkList(items, emptyText) {
    if (!items || !items.length) return `<p>${escapeHtml(emptyText)}</p>`;
    const seen = new Set();
    const unique = [];
    for (const item of items) {
      const href = item.from || item.target || item.href || "#";
      const key = `${href}|${item.label || item.text || ""}`;
      if (seen.has(key)) continue;
      seen.add(key);
      unique.push(item);
    }
    return `<ul class="panel-list">${unique.slice(0, 80).map(item => {
      const href = item.from || item.target || item.href || "#";
      const label = item.label || item.text || href;
      return `<li><a href="${href}" data-app-link>${escapeHtml(label)}</a><span class="result-doc">${escapeHtml(item.doc || "")}</span></li>`;
    }).join("")}</ul>`;
  }

  function applyReaderModes() {
    document.body.classList.toggle("columns-on", state.columns);
    document.body.classList.toggle("marginalia-on", state.marginalia);
    const columnButton = $("#toggle-columns");
    const marginaliaButton = $("#toggle-marginalia");
    if (columnButton) columnButton.setAttribute("aria-pressed", state.columns ? "true" : "false");
    if (marginaliaButton) marginaliaButton.setAttribute("aria-pressed", state.marginalia ? "true" : "false");
  }

  function buildMarginalia(reader) {
    reader.querySelectorAll(".margin-note").forEach(note => note.remove());
    for (const block of $$("p, li, blockquote", reader)) {
      const refs = [];
      const seen = new Set();
      for (const a of $$("a.reference-link[href], a.cite[href], a.gloss[href]", block)) {
        const href = normalizeHref(a.getAttribute("href"), state.currentPath);
        if (seen.has(href)) continue;
        seen.add(href);
        refs.push({ href, label: a.textContent.replace(/\s+/g, " ").trim() });
      }
      if (!refs.length) continue;
      const note = document.createElement("aside");
      note.className = "margin-note";
      note.innerHTML = refs.slice(0, 5).map(ref => `<a href="${ref.href}" data-app-link>${escapeHtml(ref.label || ref.href)}</a>`).join("");
      block.appendChild(note);
    }
  }

  function canonicalTarget(target) {
    if (!target) return "";
    if (data.nodeForAnchor[target]) return data.nodeForAnchor[target];
    const direct = data.ethicsNodes.find(n => n.href === target);
    if (direct) return direct.href;
    return target;
  }

  function ethicsNodeForTarget(target) {
    const canonical = canonicalTarget(target);
    return data.ethicsNodes.find(n => n.href === canonical) || nearestEthicsNodeFor(target);
  }

  function nodeSortKey(node) {
    const part = nodePartLabel(node).replace("Part ", "");
    const partOrder = { I: 1, II: 2, III: 3, IV: 4, V: 5 }[part] || 0;
    const kindOrder = { definition: 1, axiom: 2, proposition: 3, demonstration: 4, corollary: 5, scholium: 6 }[node.type] || 9;
    const number = Number((node.code.match(/\d+/) || [0])[0]);
    return [partOrder, number, kindOrder, node.code].join(".");
  }

  function orderedEthicsNodes() {
    return [...data.ethicsNodes].sort((a, b) => nodeSortKey(a).localeCompare(nodeSortKey(b), undefined, { numeric: true }));
  }

  function neighboringNodes(node) {
    if (!node) return { previous: null, next: null, siblings: [] };
    const peers = orderedEthicsNodes().filter(n => nodePartLabel(n) === nodePartLabel(node) && n.type === node.type);
    const index = peers.findIndex(n => n.href === node.href);
    return {
      previous: index > 0 ? peers[index - 1] : null,
      next: index >= 0 && index < peers.length - 1 ? peers[index + 1] : null,
      siblings: peers.slice(Math.max(0, index - 4), index).concat(peers.slice(index + 1, index + 5)),
    };
  }

  function relationItems(target, direction) {
    const canonical = canonicalTarget(target);
    const source = direction === "out" ? (data.outgoing[canonical] || data.outgoing[target] || []) : (data.backlinks[canonical] || data.backlinks[target] || []);
    const seen = new Set();
    return source.map(item => {
      const href = canonicalTarget(direction === "out" ? item.target : item.from);
      const node = data.ethicsNodes.find(n => n.href === href);
      return {
        href,
        text: node ? `${node.code} · ${node.type}` : (item.label || href),
        doc: node ? node.label : (item.doc || item.file || ""),
        label: item.label,
      };
    }).filter(item => {
      if (!item.href || seen.has(item.href)) return false;
      seen.add(item.href);
      return true;
    });
  }

  function compactNodeLink(node, rel) {
    if (!node) return "";
    return `<a class="trail-card ${rel || ""}" href="${nodePageHref(node)}"><span>${escapeHtml(rel || "")}</span><strong>${escapeHtml(node.code)}</strong><em>${escapeHtml(node.type)}</em></a>`;
  }

  function nodePageHref(node) {
    return node ? `/nodes/${encodeURIComponent(node.code)}.html` : "#";
  }

  function normalizeNodeCode(raw) {
    const compact = String(raw || "").trim().toUpperCase().replace(/[\s._-]+/g, "");
    if (data.ethicsNodes.some(n => n.code === compact)) return compact;
    const match = compact.match(/^([1-5])([DAP])(\d+)$/);
    if (!match) return compact;
    const roman = { "1": "I", "2": "II", "3": "III", "4": "IV", "5": "V" }[match[1]];
    return `${roman}${match[2]}${match[3]}`;
  }

  function nodeByCode(raw) {
    const code = normalizeNodeCode(raw);
    return data.ethicsNodes.find(n => n.code === code) || null;
  }

  function nodePartLabel(node) {
    if (!node) return "";
    if (node.code.startsWith("IIP") || node.code.startsWith("IID") || node.code.startsWith("IIA")) return "Part II";
    if (node.code.startsWith("IIIP") || node.code.startsWith("IIID")) return "Part III";
    if (node.code.startsWith("IV")) return "Part IV";
    if (node.code.startsWith("V")) return "Part V";
    return "Part I";
  }

  function documentLabel(path) {
    const normalized = path.replace(/^\//, "");
    const rec = data.records.find(r => r.file === normalized);
    return rec?.title || path.split("/").pop();
  }

  function nearestEthicsNodeFor(target) {
    const exact = data.ethicsNodes.find(n => n.href === target);
    if (exact) return exact;
    const parts = splitTarget(target);
    const sameFile = data.ethicsNodes.filter(n => n.href.startsWith(parts.path + "#"));
    if (!sameFile.length) return null;
    const currentId = parts.hash.slice(1);
    const current = currentId ? $("#app-document #" + CSS.escape(currentId)) : null;
    if (!current) return sameFile[0] || null;
    let nearest = null;
    for (const el of $$("#app-document [id]")) {
      const match = sameFile.find(n => n.id === el.id);
      if (match) nearest = match;
      if (el === current) break;
    }
    return nearest || sameFile[0] || null;
  }

  function renderBreadcrumbs(target = state.selectedTarget || currentSectionHref()) {
    const mount = $("#wiki-breadcrumbs");
    if (!mount) return;
    const parts = splitTarget(target);
    const node = nearestEthicsNodeFor(target);
    const crumbs = [
      { label: "Ethics", href: "/text/part0029_split_001.html#ch6d" },
      node ? { label: nodePartLabel(node), href: node.href } : { label: documentLabel(parts.path), href: parts.path },
    ];
    if (node) {
      crumbs.push({ label: node.type, href: node.href });
      crumbs.push({ label: node.code, href: node.href, current: true });
    } else if (parts.hash) {
      crumbs.push({ label: parts.hash.slice(1), href: target, current: true });
    }
    mount.innerHTML = crumbs.map((crumb, index) => {
      const sep = index ? '<span class="crumb-sep">/</span>' : "";
      const cls = crumb.current ? ' class="crumb-current"' : "";
      return `${sep}<a${cls} href="${crumb.href}" data-app-link>${escapeHtml(crumb.label)}</a>`;
    }).join("") + renderTrailStrip(node);
  }

  function renderTrailStrip(node) {
    if (!node) return "";
    const { previous, next } = neighboringNodes(node);
    return `<span class="crumb-spacer"></span><span class="crumb-trail">${compactNodeLink(previous, "Prev")}${compactNodeLink(node, "Current")}${compactNodeLink(next, "Next")}</span>`;
  }

  function nearestEthicsTarget(target) {
    if (data.nodeForAnchor[target]) return data.nodeForAnchor[target];
    if (data.anchors[target]?.id?.startsWith("cite-")) return target;
    const hash = target.split("#")[1];
    if (!hash) return target;
    const ids = $$("#app-document [id]");
    const current = $("#app-document #" + CSS.escape(hash));
    if (!current) return target;
    let best = null;
    for (const el of ids) {
      if (el === current || (el.compareDocumentPosition(current) & Node.DOCUMENT_POSITION_FOLLOWING)) {
        if (el.id && el.id.startsWith("cite-")) best = state.currentPath + "#" + el.id;
      }
    }
    return best || target;
  }

  function renderProofMap(target) {
    const panel = $("#panel-content");
    const nodeTarget = nearestEthicsTarget(target);
    const rec = data.anchors[nodeTarget] || data.anchors[target] || {};
    const outgoing = data.outgoing[nodeTarget] || data.outgoing[target] || [];
    const incoming = data.backlinks[nodeTarget] || data.backlinks[target] || [];
    const deps = outgoing.filter(o => o.target && data.ethicsNodes.some(n => n.href === o.target));
    const uses = incoming.filter(i => i.from && /part0029|part0030|part0031|part0032/.test(i.file || ""));
    const node = data.ethicsNodes.find(n => n.href === nodeTarget);
    const { previous, next, siblings } = neighboringNodes(node);
    panel.innerHTML = `
      <h2>${escapeHtml(node?.code || rec.id || "Current node")}</h2>
      <p><span class="result-doc">${escapeHtml(node?.type || rec.doc || "Ethics structure")}</span></p>
      <p>${escapeHtml(rec.label || node?.label || target)}</p>
      <h3>Trail</h3>
      <div class="trail-row">${compactNodeLink(previous, "Previous")}${compactNodeLink(node, "Current")}${compactNodeLink(next, "Next")}</div>
      <h3>Uses</h3>
      ${linkList(deps, "No explicit linked dependencies recorded for this node.")}
      <h3>Used by</h3>
      ${linkList(uses, "No later linked uses recorded for this exact node.")}
      <h3>Siblings</h3>
      ${linkList(siblings.map(n => ({ href: n.href, text: `${n.code} · ${n.type}`, doc: n.label })), "No sibling nodes available.")}
    `;
  }

  function renderContext(target) {
    const panel = $("#panel-content");
    const nodeTarget = canonicalTarget(nearestEthicsTarget(target));
    const node = data.ethicsNodes.find(n => n.href === nodeTarget) || ethicsNodeForTarget(target);
    const uses = relationItems(nodeTarget, "out").filter(i => data.ethicsNodes.some(n => n.href === i.href));
    const usedBy = relationItems(nodeTarget, "in").filter(i => data.ethicsNodes.some(n => n.href === i.href));
    const { previous, next, siblings } = neighboringNodes(node);
    panel.innerHTML = `
      <h2>${escapeHtml(node?.code || "Context")}</h2>
      <p><span class="result-doc">${escapeHtml(node ? `${nodePartLabel(node)} · ${node.type}` : target)}</span></p>
      <p>${escapeHtml(node?.label || data.anchors[target]?.label || target)}</p>
      <h3>Breadcrumb Trails</h3>
      <div class="trail-row">${compactNodeLink(previous, "Previous")}${compactNodeLink(node, "Current")}${compactNodeLink(next, "Next")}</div>
      <h3>Parents / Uses</h3>
      ${linkList(uses, "No structural parents are recorded for this node.")}
      <h3>Children / Used by</h3>
      ${linkList(usedBy, "No structural children are recorded for this node.")}
      <h3>Siblings</h3>
      ${linkList(siblings.map(n => ({ href: n.href, text: `${n.code} · ${n.type}`, doc: n.label })), "No sibling sequence nodes available.")}
    `;
  }

  function renderContextRail(target) {
    const mount = $("#context-rail");
    if (!mount) return;
    const nodeTarget = canonicalTarget(nearestEthicsTarget(target));
    const node = data.ethicsNodes.find(n => n.href === nodeTarget) || ethicsNodeForTarget(target);
    const uses = relationItems(nodeTarget, "out").filter(i => data.ethicsNodes.some(n => n.href === i.href));
    const usedBy = relationItems(nodeTarget, "in").filter(i => data.ethicsNodes.some(n => n.href === i.href));
    const { previous, next } = neighboringNodes(node);
    mount.innerHTML = `
      <button type="button" class="rail-handle" data-rail-tab="context" aria-label="Open context">Context</button>
      <div class="rail-body">
        <strong>${escapeHtml(node?.code || "Ethics")}</strong>
        <span>${escapeHtml(node ? `${nodePartLabel(node)} · ${node.type}` : "Current target")}</span>
        <div class="rail-counts">
          <button type="button" data-rail-tab="context">${uses.length} uses</button>
          <button type="button" data-rail-tab="incoming">${usedBy.length} used by</button>
        </div>
        <div class="rail-jump">${compactNodeLink(previous, "Prev")}${compactNodeLink(next, "Next")}</div>
      </div>
    `;
  }

  function ethicsOnly(items) {
    return items.filter(item => data.ethicsNodes.some(n => n.href === item.href));
  }

  function transitiveItems(startTarget, direction, maxDepth = 8) {
    const start = canonicalTarget(nearestEthicsTarget(startTarget));
    const queue = [{ href: start, depth: 0, path: [] }];
    const seen = new Set([start]);
    const rows = [];
    while (queue.length) {
      const current = queue.shift();
      if (current.depth >= maxDepth) continue;
      for (const item of ethicsOnly(relationItems(current.href, direction))) {
        if (seen.has(item.href)) continue;
        seen.add(item.href);
        const node = data.ethicsNodes.find(n => n.href === item.href);
        const path = current.path.concat(node?.code || item.text || item.href);
        rows.push({ ...item, depth: current.depth + 1, path });
        queue.push({ href: item.href, depth: current.depth + 1, path });
      }
    }
    return rows;
  }

  function chainList(items, emptyText) {
    if (!items.length) return `<p>${escapeHtml(emptyText)}</p>`;
    return `<ol class="chain-list">${items.slice(0, 120).map(item => `
      <li style="--depth:${Math.min(item.depth, 8)}">
        <a href="${item.href}" data-app-link>${escapeHtml(item.text || item.href)}</a>
        <span class="result-doc">${escapeHtml(`depth ${item.depth}${item.path?.length ? " · " + item.path.join(" -> ") : ""}`)}</span>
      </li>
    `).join("")}</ol>`;
  }

  function renderChains(target) {
    const panel = $("#panel-content");
    const nodeTarget = canonicalTarget(nearestEthicsTarget(target));
    const node = data.ethicsNodes.find(n => n.href === nodeTarget) || ethicsNodeForTarget(target);
    const ancestors = transitiveItems(nodeTarget, "out");
    const descendants = transitiveItems(nodeTarget, "in");
    panel.innerHTML = `
      <h2>${escapeHtml(node?.code || "Dependency Chains")}</h2>
      <p><span class="result-doc">${ancestors.length} transitive ancestor${ancestors.length === 1 ? "" : "s"} · ${descendants.length} transitive descendant${descendants.length === 1 ? "" : "s"}</span></p>
      <h3>All Ancestors</h3>
      ${chainList(ancestors, "No transitive ancestors recorded.")}
      <h3>All Descendants</h3>
      ${chainList(descendants, "No transitive descendants recorded.")}
    `;
  }

  function renderMatrix(target) {
    const panel = $("#panel-content");
    const nodeTarget = canonicalTarget(nearestEthicsTarget(target));
    const node = data.ethicsNodes.find(n => n.href === nodeTarget) || ethicsNodeForTarget(target);
    const rowNodes = ethicsOnly(relationItems(nodeTarget, "out")).slice(0, 28);
    const colNodes = [{ href: nodeTarget, text: node ? `${node.code} · ${node.type}` : "Current", doc: node?.label || "" }]
      .concat(ethicsOnly(relationItems(nodeTarget, "in")).slice(0, 10));
    const depSets = new Map(colNodes.map(col => [col.href, new Set(ethicsOnly(relationItems(col.href, "out")).map(item => item.href))]));
    panel.innerHTML = `
      <h2>${escapeHtml(node?.code || "Usage Matrix")}</h2>
      <p><span class="result-doc">Rows are dependencies. Columns are this node and direct users.</span></p>
      <div class="matrix-scroll">
        <table class="usage-matrix">
          <thead><tr><th>Dependency</th>${colNodes.map(col => `<th><a href="${col.href}" data-app-link>${escapeHtml((col.text || col.href).split(" · ")[0])}</a></th>`).join("")}</tr></thead>
          <tbody>
            ${rowNodes.map(row => `<tr><th><a href="${row.href}" data-app-link>${escapeHtml((row.text || row.href).split(" · ")[0])}</a></th>${colNodes.map(col => `<td class="${depSets.get(col.href)?.has(row.href) ? "has-edge" : ""}">${depSets.get(col.href)?.has(row.href) ? "use" : ""}</td>`).join("")}</tr>`).join("")}
          </tbody>
        </table>
      </div>
    `;
  }

  function graphNodeLabel(item) {
    return escapeHtml((item.text || item.href || "").split(" · ")[0]);
  }

  function renderGraph(target) {
    const panel = $("#panel-content");
    const nodeTarget = canonicalTarget(nearestEthicsTarget(target));
    const node = data.ethicsNodes.find(n => n.href === nodeTarget) || ethicsNodeForTarget(target);
    const deps = ethicsOnly(relationItems(nodeTarget, "out")).slice(0, 10);
    const usedBy = ethicsOnly(relationItems(nodeTarget, "in")).slice(0, 10);
    const left = deps.map((item, i) => ({ ...item, x: 90, y: 42 + i * 34 }));
    const right = usedBy.map((item, i) => ({ ...item, x: 370, y: 42 + i * 34 }));
    const centerY = Math.max(95, 42 + Math.max(left.length, right.length) * 17);
    panel.innerHTML = `
      <h2>${escapeHtml(node?.code || "Graph")}</h2>
      <p><span class="result-doc">Local neighborhood: dependencies point into the selected node; users point out.</span></p>
      <svg class="node-graph" viewBox="0 0 460 ${Math.max(210, centerY * 2)}" role="img" aria-label="Node dependency graph">
        ${left.map(n => `<line x1="${n.x + 54}" y1="${n.y}" x2="220" y2="${centerY}" />`).join("")}
        ${right.map(n => `<line x1="240" y1="${centerY}" x2="${n.x - 54}" y2="${n.y}" />`).join("")}
        ${left.map(n => `<a href="${n.href}" data-app-link><circle cx="${n.x}" cy="${n.y}" r="18" class="dep-node"/><text x="${n.x}" y="${n.y + 4}" text-anchor="middle">${graphNodeLabel(n)}</text></a>`).join("")}
        <a href="${nodePageHref(node)}"><circle cx="230" cy="${centerY}" r="26" class="focus-node"/><text x="230" y="${centerY + 5}" text-anchor="middle">${escapeHtml(node?.code || "node")}</text></a>
        ${right.map(n => `<a href="${n.href}" data-app-link><circle cx="${n.x}" cy="${n.y}" r="18" class="use-node"/><text x="${n.x}" y="${n.y + 4}" text-anchor="middle">${graphNodeLabel(n)}</text></a>`).join("")}
      </svg>
    `;
  }

  function renderDossier(target) {
    const panel = $("#panel-content");
    const nodeTarget = canonicalTarget(nearestEthicsTarget(target));
    const node = data.ethicsNodes.find(n => n.href === nodeTarget) || ethicsNodeForTarget(target);
    const raw = data.outgoing[nodeTarget] || data.outgoing[target] || [];
    const notes = [];
    const glossary = [];
    const resources = [];
    for (const edge of raw) {
      const href = edge.target || edge.href;
      if (!href || data.ethicsNodes.some(n => n.href === canonicalTarget(href))) continue;
      const item = { href, text: edge.label || href, doc: edge.doc || edge.file || "" };
      if (href.includes("part0033.html")) notes.push(item);
      else if ((edge.classes || "").includes("gloss")) glossary.push(item);
      else if (href.startsWith("/text/")) resources.push(item);
    }
    panel.innerHTML = `
      <h2>${escapeHtml(node?.code || "Study Dossier")}</h2>
      <p><span class="result-doc">${notes.length} note${notes.length === 1 ? "" : "s"} · ${glossary.length} glossary term${glossary.length === 1 ? "" : "s"} · ${resources.length} resource${resources.length === 1 ? "" : "s"}</span></p>
      <h3>Curley / Editorial Notes</h3>
      ${linkList(notes, "No linked editorial notes recorded for this node.")}
      <h3>Glossary Terms</h3>
      ${linkList(glossary, "No linked glossary terms recorded for this node.")}
      <h3>Other Linked Resources</h3>
      ${linkList(resources, "No other linked resources recorded for this node.")}
      <h3>Commentary Slot</h3>
      <p>Use the canonical node page for full dossier context and future interpretive commentary.</p>
    `;
  }

  function positionHoverCard(event) {
    if (!hoverCard) return;
    const pad = 14;
    const rect = hoverCard.getBoundingClientRect();
    let left = event.clientX + 18;
    let top = event.clientY + 18;
    if (left + rect.width + pad > window.innerWidth) left = Math.max(pad, event.clientX - rect.width - 18);
    if (top + rect.height + pad > window.innerHeight) top = Math.max(pad, window.innerHeight - rect.height - pad);
    hoverCard.style.left = left + "px";
    hoverCard.style.top = top + "px";
  }

  function hideHoverCard() {
    clearTimeout(hoverTimer);
    hoverTimer = window.setTimeout(() => {
      if (hoverCard) hoverCard.remove();
      hoverCard = null;
    }, 140);
  }

  function showHoverCard(target, label, event) {
    clearTimeout(hoverTimer);
    hoverTimer = window.setTimeout(async () => {
      const rec = data.anchors[target] || {};
      const incoming = data.backlinks[target] || [];
      const outgoing = data.outgoing[target] || [];
      const snippet = await targetSnippet(target);
      if (!hoverCard) {
        hoverCard = document.createElement("div");
        hoverCard.className = "hover-card";
        document.body.appendChild(hoverCard);
        hoverCard.addEventListener("mouseenter", () => clearTimeout(hoverTimer));
        hoverCard.addEventListener("mouseleave", hideHoverCard);
      }
      hoverCard.innerHTML = `
        <h2>${escapeHtml(rec.label || label || target)}</h2>
        <span class="result-doc">${escapeHtml(rec.doc || target)}</span>
        ${snippet ? `<p>${escapeHtml(snippet)}</p>` : `<p>No readable preview available for this anchor.</p>`}
        <p>${incoming.length} backlink${incoming.length === 1 ? "" : "s"} · ${outgoing.length} outgoing link${outgoing.length === 1 ? "" : "s"}</p>
        <div class="hover-actions">
          <a href="${target}" data-app-link>Open</a>
          <button type="button" data-copy="${target}">Copy link</button>
          <button type="button" data-pin="${target}">Pin in panel</button>
        </div>
      `;
      positionHoverCard(event);
    }, 180);
  }

  function renderPanel() {
    const panel = $("#panel-content");
    if (!panel) return;
    const target = state.selectedTarget || currentSectionHref();
    const rec = data.anchors[target] || {};
    const incoming = data.backlinks[target] || [];
    const outgoing = data.outgoing[target] || data.outgoing[currentSectionHref()] || [];
    $$(".panel-tabs button").forEach(btn => btn.classList.toggle("active", btn.dataset.tab === state.activeTab));

    if (state.activeTab === "incoming") {
      panel.innerHTML = `<h2>Backlinks</h2><p>${escapeHtml(rec.label || target)}</p>${linkList(incoming, "No incoming references recorded for this exact anchor.")}`;
      return;
    }
    if (state.activeTab === "context") {
      renderContext(target);
      return;
    }
    if (state.activeTab === "dossier") {
      renderDossier(target);
      return;
    }
    if (state.activeTab === "proof") {
      renderProofMap(target);
      return;
    }
    if (state.activeTab === "chains") {
      renderChains(target);
      return;
    }
    if (state.activeTab === "matrix") {
      renderMatrix(target);
      return;
    }
    if (state.activeTab === "graph") {
      renderGraph(target);
      return;
    }
    if (state.activeTab === "outgoing") {
      panel.innerHTML = `<h2>Outgoing Links</h2><p>${escapeHtml(rec.label || "Current section")}</p>${linkList(outgoing, "No outgoing references recorded for this section.")}`;
      return;
    }
    if (state.activeTab === "search") {
      renderSearchResults(state.lastSearch || $("#global-search")?.value || "");
      return;
    }
    const targetText = rec.label || target;
    const exact = target.split("#")[1] ? $("#app-document #" + CSS.escape(target.split("#")[1])) : null;
    const visibleSnippet = exact ? exact.textContent.replace(/\s+/g, " ").trim().slice(0, 700) : "";
    panel.innerHTML = `
      <h2>${escapeHtml(targetText)}</h2>
      <p><span class="result-doc">${escapeHtml(rec.doc || state.currentPath)}</span></p>
      ${visibleSnippet ? `<p>${escapeHtml(visibleSnippet)}</p>` : ""}
      <p><a href="${target}" data-app-link>Open target</a></p>
      <h3>Incoming</h3>
      ${linkList(incoming.slice(0, 10), "No incoming references recorded.")}
      <h3>Outgoing</h3>
      ${linkList(outgoing.slice(0, 10), "No outgoing references recorded.")}
    `;
  }

  function renderSearchResults(query) {
    const panel = $("#panel-content");
    if (!panel) return;
    state.lastSearch = query.trim();
    if (!state.lastSearch) {
      panel.innerHTML = `<h2>Search</h2><p>Type in the search field to search the Ethics-centered corpus and referenced context.</p>`;
      return;
    }
    const q = state.lastSearch.toLowerCase();
    const results = data.search.filter(row => row.text.toLowerCase().includes(q) || row.doc.toLowerCase().includes(q)).slice(0, 120);
    panel.innerHTML = `<h2>Search</h2><p>${results.length} result${results.length === 1 ? "" : "s"} for “${escapeHtml(state.lastSearch)}”.</p>${linkList(results, "No matches.")}`;
  }

  function renderEthicsContents() {
    const mount = $("#ethics-node-contents");
    if (!mount) return;
    const groups = new Map();
    for (const node of data.ethicsNodes) {
      const part = node.code.startsWith("IIP") || node.code.startsWith("IID") || node.code.startsWith("IIA") ? "Part II"
        : node.code.startsWith("IIIP") || node.code.startsWith("IIID") ? "Part III"
        : node.code.startsWith("IV") ? "Part IV"
        : node.code.startsWith("V") ? "Part V"
        : "Part I";
      if (!groups.has(part)) groups.set(part, []);
      groups.get(part).push(node);
    }
    mount.innerHTML = Array.from(groups.entries()).map(([part, nodes]) => `
      <section class="node-group">
        <h3>${escapeHtml(part)}</h3>
        ${nodes.map(node => `<a href="${nodePageHref(node)}" title="${escapeHtml(node.label)}"><span class="node-code">${escapeHtml(node.code)}</span><span class="node-label">${escapeHtml(node.type)}</span></a>`).join("")}
      </section>
    `).join("");
  }

  function init() {
    const params = new URLSearchParams(location.search);
    const initial = params.get("doc") || localStorage.getItem("spinoza:lastTarget") || "/text/part0029_split_001.html#ch6d";
    applyReaderModes();
    loadDocument(initial, false);

    document.addEventListener("click", event => {
      const tab = event.target.closest(".panel-tabs button[data-tab]");
      if (tab) {
        state.activeTab = tab.dataset.tab;
        renderPanel();
        return;
      }
      const railTab = event.target.closest("[data-rail-tab]");
      if (railTab) {
        state.activeTab = railTab.dataset.railTab;
        renderPanel();
        return;
      }
      const copy = event.target.closest("[data-copy]");
      if (copy) {
        const target = copy.dataset.copy;
        navigator.clipboard && navigator.clipboard.writeText(location.origin + target);
        copy.textContent = "Copied";
        window.setTimeout(() => { copy.textContent = "Copy link"; }, 1200);
        return;
      }
      const pin = event.target.closest("[data-pin]");
      if (pin) {
        selectTarget(pin.dataset.pin);
        hideHoverCard();
        return;
      }
      const a = event.target.closest("a[href]");
      if (!a) return;
      const href = normalizeHref(a.getAttribute("href"), state.currentPath);
      if (href.startsWith("/text/") || href.startsWith("/titlepage")) {
        event.preventDefault();
        selectTarget(href);
        loadDocument(href, true);
      }
    });

    document.addEventListener("mouseover", event => {
      const a = event.target.closest("a.reference-link[href], a[data-app-link][href]");
      if (!a) return;
      const target = normalizeHref(a.getAttribute("href"), state.currentPath);
      selectTarget(target);
      showHoverCard(target, a.textContent.trim(), event);
    });

    document.addEventListener("mousemove", event => {
      if (hoverCard) positionHoverCard(event);
    });

    document.addEventListener("mouseout", event => {
      const a = event.target.closest("a.reference-link[href], a[data-app-link][href]");
      if (a) hideHoverCard();
    });

    $("#global-search")?.addEventListener("input", event => {
      state.activeTab = "search";
      renderSearchResults(event.target.value);
    });

    $("#global-search")?.addEventListener("keydown", event => {
      if (event.key !== "Enter") return;
      const node = nodeByCode(event.target.value);
      if (!node) return;
      event.preventDefault();
      location.href = nodePageHref(node);
    });

    $("#open-apparatus")?.addEventListener("click", () => {
      state.activeTab = "incoming";
      selectTarget(currentSectionHref());
    });

    $("#toggle-columns")?.addEventListener("click", () => {
      state.columns = !state.columns;
      localStorage.setItem("spinoza:columns", state.columns ? "1" : "0");
      applyReaderModes();
    });

    $("#toggle-marginalia")?.addEventListener("click", () => {
      state.marginalia = !state.marginalia;
      localStorage.setItem("spinoza:marginalia", state.marginalia ? "1" : "0");
      applyReaderModes();
    });

    $("#app-reader")?.addEventListener("scroll", () => {
      if (state.activeTab === "target") selectTarget(currentSectionHref());
      else renderBreadcrumbs(currentSectionHref());
    }, { passive: true });

    window.addEventListener("popstate", event => {
      const params = new URLSearchParams(location.search);
      const target = event.state?.target || params.get("doc") || "/text/part0029_split_001.html#ch6d";
      loadDocument(target, false);
    });
  }

  renderEthicsContents();
  init();
})();

"""


def main() -> None:
    if OUT.exists():
        for child in OUT.iterdir():
            if child.name == "build_spinoza_ethics_site.py":
                continue
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()

    (OUT / "text").mkdir(parents=True, exist_ok=True)
    records, anchors, backlinks, outgoing, search, ethics_nodes, node_for_anchor = collect_records()
    write_static(records, anchors, backlinks, outgoing, search, ethics_nodes, node_for_anchor)
    write_graph_db(records, anchors, backlinks, outgoing, search, ethics_nodes, node_for_anchor)
    write_graph_model_note()

    for rel in FILES:
        target = OUT / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(enhance_doc(rel, backlinks), encoding="utf-8")

    for asset_dir in ["images", "fonts"]:
        src_dir = SOURCE / asset_dir
        if src_dir.exists():
            shutil.copytree(src_dir, OUT / asset_dir, dirs_exist_ok=True)
    for asset in ["cover.jpeg"]:
        if (SOURCE / asset).exists():
            shutil.copy2(SOURCE / asset, OUT / asset)

    report = {
        "source": str(SOURCE),
        "output": str(OUT),
        "files": len(FILES),
        "anchors": len(anchors),
        "linked_targets": len([k for k, v in backlinks.items() if v]),
        "incoming_references": sum(len(v) for v in backlinks.values()),
        "outgoing_reference_sources": len(outgoing),
        "search_records": len(search),
        "ethics_nodes": len(ethics_nodes),
        "node_anchor_mappings": len(node_for_anchor),
    }
    (OUT / "build-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
