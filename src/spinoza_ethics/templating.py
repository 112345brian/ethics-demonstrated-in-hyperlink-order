"""Loading of the packaged HTML templates and static assets.

Templates use :class:`string.Template` placeholders (``$name``) rather than
f-strings so the markup can live in real ``.html`` files.  The markup contains
no literal ``$``, so no escaping is required.
"""

from __future__ import annotations

from importlib import resources
from string import Template

PACKAGE = __package__ or "spinoza_ethics"


def template_text(name: str) -> str:
    """Raw text of a packaged template."""
    return resources.files(PACKAGE).joinpath("templates", name).read_text(encoding="utf-8")


def static_text(name: str) -> str:
    """Raw text of a packaged static asset."""
    return resources.files(PACKAGE).joinpath("static", name).read_text(encoding="utf-8")


def render_template(name: str, /, **values: object) -> str:
    """Substitute ``values`` into the named template.

    Uses ``substitute`` (not ``safe_substitute``) so a typo in a placeholder
    fails the build instead of shipping a literal ``$name`` to the browser.
    """
    return Template(template_text(name)).substitute(values)
