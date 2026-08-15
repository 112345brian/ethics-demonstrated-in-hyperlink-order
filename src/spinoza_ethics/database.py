"""Derived SQLite mirror of the reference graph.

Recursive CTEs give dependency chains and FTS5 gives local full-text search,
which is enough for the scholarly queries without running a server.
"""

from __future__ import annotations

import sqlite3

from .config import CORE_FILES, BuildConfig
from .corpus import Corpus
from .graph import edge_type_for


def write_database(config: BuildConfig, corpus: Corpus) -> None:
    """Write ``spinoza-ethics.db`` from the collected corpus."""
    records = corpus.records
    anchors = corpus.anchors
    outgoing = corpus.outgoing
    search = corpus.search
    ethics_nodes = corpus.ethics_nodes
    node_for_anchor = corpus.node_for_anchor
    db_path = config.output / "spinoza-ethics.db"
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
