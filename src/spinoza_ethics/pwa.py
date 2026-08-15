"""Progressive-web-app files: the manifest and the offline service worker."""

from __future__ import annotations

import json

from .config import BuildConfig
from .templating import render_template, static_text

MANIFEST = {
    "name": "Spinoza Ethics Workbench",
    "short_name": "Ethics",
    "description": "Offline-capable scholarly workbench for Spinoza's Ethics.",
    "start_url": "/index.html",
    "scope": "/",
    "display": "standalone",
    "background_color": "#fbfaf7",
    "theme_color": "#fbfaf7",
    "orientation": "any",
    "icons": [
        {"src": "/cover.jpeg", "sizes": "512x512", "type": "image/jpeg", "purpose": "any"}
    ],
}

#: Never precached: build metadata and the (large) derived database.
PRECACHE_EXCLUDE_SUFFIXES = (".tar.gz",)
PRECACHE_EXCLUDE_NAMES = ("spinoza-ethics.db",)


def precache_urls(config: BuildConfig) -> list[str]:
    """Every already-written output file, as a site-absolute URL."""
    paths = []
    for path in sorted(config.output.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(config.output).as_posix()
        if rel.startswith(".git/") or rel.endswith(PRECACHE_EXCLUDE_SUFFIXES):
            continue
        if rel in PRECACHE_EXCLUDE_NAMES:
            continue
        paths.append("/" + rel)
    if "/index.html" not in paths:
        paths.insert(0, "/index.html")
    return paths


def write_pwa_files(config: BuildConfig) -> None:
    """Write the manifest, the registration shim, and the service worker.

    Must run after every other output file exists: the service worker's
    precache list is built by scanning the output tree.
    """
    assets = config.output / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    (config.output / "manifest.webmanifest").write_text(
        json.dumps(MANIFEST, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (assets / "pwa.js").write_text(static_text("pwa.js"), encoding="utf-8")

    urls = precache_urls(config)
    worker = render_template(
        "sw.js",
        cache_name=json.dumps(f"spinoza-ethics-workbench-v{len(urls)}"),
        precache_urls=json.dumps(urls, ensure_ascii=False),
    )
    (config.output / "sw.js").write_text(worker, encoding="utf-8")
