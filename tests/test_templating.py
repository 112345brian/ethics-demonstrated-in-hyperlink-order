"""Template loading and strict placeholder substitution."""

from __future__ import annotations

from importlib import resources

import pytest

from spinoza_ethics import templating
from spinoza_ethics.templating import PACKAGE, render_template, static_text, template_text


def packaged_names(subdir: str) -> list[str]:
    root = resources.files(PACKAGE).joinpath(subdir)
    return sorted(entry.name for entry in root.iterdir() if entry.is_file())


def test_render_template_substitutes_values(monkeypatch):
    monkeypatch.setattr(templating, "template_text", lambda name: "<h1>$title</h1><p>$body</p>")
    assert render_template("x.html", title="Ethics", body="hi") == "<h1>Ethics</h1><p>hi</p>"


def test_render_template_raises_key_error_on_missing_placeholder(monkeypatch):
    """``substitute`` (not ``safe_substitute``) so a typo fails the build."""
    monkeypatch.setattr(templating, "template_text", lambda name: "<h1>$title</h1><p>$body</p>")
    with pytest.raises(KeyError):
        render_template("x.html", title="Ethics")


def test_render_template_ignores_extra_values(monkeypatch):
    monkeypatch.setattr(templating, "template_text", lambda name: "<h1>$title</h1>")
    assert render_template("x.html", title="Ethics", unused="x") == "<h1>Ethics</h1>"


def test_there_are_packaged_templates():
    assert packaged_names("templates")


@pytest.mark.parametrize("name", packaged_names("templates"))
def test_every_packaged_template_is_readable(name):
    assert template_text(name).strip()


@pytest.mark.parametrize("name", packaged_names("static"))
def test_every_packaged_static_asset_is_readable(name):
    assert static_text(name).strip()


def test_template_text_raises_for_a_missing_template():
    with pytest.raises(FileNotFoundError):
        template_text("no-such-template.html")
