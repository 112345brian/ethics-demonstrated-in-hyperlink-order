# Spinoza Ethics Graph Model

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
