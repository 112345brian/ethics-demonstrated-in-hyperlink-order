"""Reusable HTML fragments shared by the node pages and dossiers."""

from __future__ import annotations

import html
import re
from pathlib import Path

from ..config import BuildConfig
from ..xmlutil import absolutize_href, lname, node_to_html, parse


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


def clean_node_excerpt(text: str, limit: int = 170) -> str:
    cleaned = re.sub(r"\[\d+\]\s*", "", text or "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned if len(cleaned) <= limit else cleaned[: limit - 1].rstrip() + "…"


def chain_link_list(items: list[dict], empty_text: str, root_code: str, direction: str) -> str:
    if not items:
        return f"<p>{html.escape(empty_text)}</p>"
    arrow = "←" if direction == "out" else "→"
    relation = "upstream" if direction == "out" else "downstream"
    rows = []
    for item in items[:160]:
        path = [root_code] + item.get("path", [])
        chain = f" {arrow} ".join(path)
        depth = item.get("depth", 1)
        step_label = f"{depth} step{'s' if depth != 1 else ''} {relation}"
        excerpt = clean_node_excerpt(item.get("doc", ""))
        meta = f"{step_label} · {chain}"
        if excerpt:
            meta += f" · {excerpt}"
        rows.append(
            f'<li style="--depth:{min(item.get("depth", 1), 8)}">'
            f'<a href="{html.escape(item["href"])}">{html.escape(item.get("code") or item["text"])}</a>'
            f'<span class="result-doc">{html.escape(meta)}</span></li>'
        )
    return f'<ol class="chain-list">{"".join(rows)}</ol>'


def render_node_source_html(config: BuildConfig, node: dict) -> str:
    tree = parse(config.source / node["file"])
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


def render_anchor_context_html(config: BuildConfig, href: str) -> str:
    if not href.startswith("/"):
        return ""
    path, _, frag = href.removeprefix("/").partition("#")
    if not frag or not (config.source / path).exists():
        return ""
    tree = parse(config.source / path)
    root = tree.getroot()
    parents = {child: parent for parent in root.iter() for child in list(parent)}
    target = None
    for el in root.iter():
        if el.attrib.get("id") == frag:
            target = el
            break
    if target is None:
        return ""
    if (
        lname(target.tag) == "a" or lname(target.tag) not in {"p", "li", "blockquote", "section"}
    ) and parents.get(target) is not None:
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


def resource_cards(config: BuildConfig, items: list[dict], empty_text: str) -> str:
    if not items:
        return f"<p>{html.escape(empty_text)}</p>"
    cards = []
    seen = set()
    for item in items[:40]:
        href = item["href"]
        if href in seen:
            continue
        seen.add(href)
        body = render_anchor_context_html(config, href)
        if not body:
            body = f'<p>{html.escape(item.get("label") or href)}</p>'
        cards.append(
            f'<article class="resource-card"><h3><a href="{html.escape(href)}">{html.escape(item["title"])}</a></h3>'
            f'<div class="resource-body">{body}</div></article>'
        )
    return f'<div class="resource-list">{"".join(cards)}</div>'
