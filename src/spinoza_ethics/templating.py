"""Loading of the packaged HTML templates and static assets.

Templates use :class:`string.Template` placeholders (``$name``) rather than
f-strings so the markup can live in real ``.html`` files.  The markup contains
no literal ``$``, so no escaping is required.
"""

from __future__ import annotations

import json
from importlib import resources
from string import Template

from .config import BuildConfig

PACKAGE = __package__ or "spinoza_ethics"


def template_text(name: str) -> str:
    """Raw text of a packaged template."""
    return resources.files(PACKAGE).joinpath("templates", name).read_text(encoding="utf-8")


def static_text(name: str) -> str:
    """Raw text of a packaged static asset."""
    return resources.files(PACKAGE).joinpath("static", name).read_text(encoding="utf-8")


def site_url(base_path: str, path: str) -> str:
    """Prefix a root-relative path with the site's deployment base path.

    Only root-relative paths (``/nodes/IP11.html``) are prefixed; scheme-
    qualified, fragment-only, and already-prefixed paths pass through
    unchanged. With ``base_path=""`` this is the identity function, so a
    root-deployed build is unaffected byte-for-byte.
    """
    if not base_path or not path or not path.startswith("/"):
        return path
    if path == base_path or path.startswith(base_path + "/"):
        return path
    return base_path + path


def render_template(name: str, /, **values: object) -> str:
    """Substitute ``values`` into the named template.

    Uses ``substitute`` (not ``safe_substitute``) so a typo in a placeholder
    fails the build instead of shipping a literal ``$name`` to the browser.
    """
    return Template(template_text(name)).substitute(values)


def render_page(config: BuildConfig, name: str, /, **values: object) -> str:
    """Render a top-level HTML page, injecting the deployment base path.

    Every page template accepts ``$base`` (prefix for root-relative hrefs,
    "" for a root deploy) and ``$base_json`` (the same value, JSON-encoded,
    for the inline ``window.SPINOZA_BASE_PATH`` script the client JS reads).
    """
    return render_template(
        name,
        base=config.base_path,
        base_json=json.dumps(config.base_path),
        **values,
    )
