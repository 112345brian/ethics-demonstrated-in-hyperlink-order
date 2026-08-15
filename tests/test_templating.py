"""Template loading and strict placeholder substitution."""

from __future__ import annotations

from importlib import resources

import pytest

from spinoza_ethics import templating
from spinoza_ethics.config import BuildConfig
from spinoza_ethics.templating import (
    PACKAGE,
    render_page,
    render_template,
    site_url,
    static_text,
    template_text,
)


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


# --- site_url --------------------------------------------------------------


def test_site_url_is_identity_with_no_base_path():
    assert site_url("", "/nodes/IP1.html") == "/nodes/IP1.html"


def test_site_url_prefixes_a_root_relative_path():
    assert site_url("/repo", "/nodes/IP1.html") == "/repo/nodes/IP1.html"


def test_site_url_leaves_a_fragment_only_href_unchanged():
    assert site_url("/repo", "#top") == "#top"


def test_site_url_leaves_an_external_scheme_unchanged():
    assert site_url("/repo", "https://example.com/x") == "https://example.com/x"


def test_site_url_leaves_empty_string_unchanged():
    assert site_url("/repo", "") == ""


def test_site_url_does_not_double_prefix_an_already_prefixed_path():
    assert site_url("/repo", "/repo/nodes/IP1.html") == "/repo/nodes/IP1.html"


# --- render_page -------------------------------------------------------------


def test_render_page_injects_base_and_base_json(monkeypatch):
    monkeypatch.setattr(templating, "template_text", lambda name: "$base|$base_json|$title")
    config = BuildConfig.create(".", ".", base_path="/repo")
    assert render_page(config, "x.html", title="Ethics") == '/repo|"/repo"|Ethics'


def test_render_page_with_no_base_path_matches_render_template(monkeypatch):
    monkeypatch.setattr(templating, "template_text", lambda name: "$base|$base_json|$title")
    config = BuildConfig.create(".", ".")
    assert render_page(config, "x.html", title="Ethics") == '|""|Ethics'
