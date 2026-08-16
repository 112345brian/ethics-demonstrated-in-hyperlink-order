"""Progressive-web-app files: the manifest and the offline service worker."""

from __future__ import annotations

import hashlib
import json

from .config import BuildConfig
from .templating import render_template, site_url, static_text

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


def manifest_for(config: BuildConfig) -> dict:
    """The web app manifest, with start_url/scope/icon prefixed for the deploy base path."""
    base = config.base_path
    manifest = json.loads(json.dumps(MANIFEST))
    manifest["start_url"] = site_url(base, manifest["start_url"])
    manifest["scope"] = site_url(base, manifest["scope"])
    for icon in manifest["icons"]:
        icon["src"] = site_url(base, icon["src"])
    return manifest

#: Never precached: build metadata and the (large) derived database.
PRECACHE_EXCLUDE_SUFFIXES = (".tar.gz",)
PRECACHE_EXCLUDE_NAMES = ("spinoza-ethics.db",)


def precache_urls(config: BuildConfig) -> list[str]:
    """Every already-written output file, as a browser-fetchable URL."""
    paths = []
    for path in sorted(config.output.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(config.output).as_posix()
        if rel.startswith(".git/") or rel.endswith(PRECACHE_EXCLUDE_SUFFIXES):
            continue
        if rel in PRECACHE_EXCLUDE_NAMES:
            continue
        paths.append(site_url(config.base_path, "/" + rel))
    index_url = site_url(config.base_path, "/index.html")
    if index_url not in paths:
        paths.insert(0, index_url)
    return paths


def content_fingerprint(config: BuildConfig, urls: list[str]) -> str:
    """A short hash of every precached file's actual bytes.

    Used as the cache name suffix so *any* content change -- not just a
    change in file count -- produces a different sw.js, which is what
    makes the browser notice there's a new service worker to install and
    replace its cache. A count-based version number stays identical
    across a same-file-count content edit, so browsers never re-fetch and
    users are stuck on stale cached assets indefinitely.
    """
    digest = hashlib.sha256()
    for url in sorted(urls):
        rel = url[len(config.base_path):] if config.base_path else url
        path = config.output / rel.lstrip("/")
        if path.is_file():
            digest.update(path.read_bytes())
    return digest.hexdigest()[:12]


def write_pwa_files(config: BuildConfig) -> None:
    """Write the manifest, the registration shim, and the service worker.

    Must run after every other output file exists: the service worker's
    precache list is built by scanning the output tree.
    """
    assets = config.output / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    (config.output / "manifest.webmanifest").write_text(
        json.dumps(manifest_for(config), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (assets / "pwa.js").write_text(static_text("pwa.js"), encoding="utf-8")

    urls = precache_urls(config)
    fingerprint = content_fingerprint(config, urls)
    worker = render_template(
        "sw.js",
        cache_name=json.dumps(f"spinoza-ethics-workbench-{fingerprint}"),
        precache_urls=json.dumps(urls, ensure_ascii=False),
    )
    (config.output / "sw.js").write_text(worker, encoding="utf-8")
