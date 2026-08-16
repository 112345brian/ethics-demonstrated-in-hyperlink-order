"""Service-worker precache list."""

from __future__ import annotations

from spinoza_ethics.config import BuildConfig
from spinoza_ethics.pwa import content_fingerprint, precache_urls


def config_for(tmp_path, files: dict[str, str]) -> BuildConfig:
    output = tmp_path / "build"
    for rel, content in files.items():
        path = output / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    output.mkdir(parents=True, exist_ok=True)
    return BuildConfig.create(source=tmp_path / "source", output=output)


def test_returns_site_absolute_sorted_urls(tmp_path):
    config = config_for(tmp_path, {
        "index.html": "x",
        "assets/site.css": "x",
        "nodes/IP1.html": "x",
    })
    assert precache_urls(config) == ["/assets/site.css", "/index.html", "/nodes/IP1.html"]


def test_excludes_the_derived_database(tmp_path):
    config = config_for(tmp_path, {"index.html": "x", "spinoza-ethics.db": "x"})
    assert precache_urls(config) == ["/index.html"]


def test_excludes_tarballs(tmp_path):
    config = config_for(tmp_path, {"index.html": "x", "spinoza-ethics-site.tar.gz": "x"})
    assert precache_urls(config) == ["/index.html"]


def test_excludes_a_git_directory(tmp_path):
    config = config_for(tmp_path, {"index.html": "x", ".git/config": "x"})
    assert precache_urls(config) == ["/index.html"]


def test_always_includes_index_html_even_when_absent(tmp_path):
    config = config_for(tmp_path, {"assets/site.css": "x"})
    assert precache_urls(config)[0] == "/index.html"


def test_index_html_is_not_duplicated(tmp_path):
    config = config_for(tmp_path, {"index.html": "x"})
    assert precache_urls(config).count("/index.html") == 1


def test_directories_are_not_listed(tmp_path):
    config = config_for(tmp_path, {"nodes/IP1.html": "x"})
    assert "/nodes" not in precache_urls(config)


def test_empty_output_still_yields_index(tmp_path):
    config = config_for(tmp_path, {})
    assert precache_urls(config) == ["/index.html"]


# --- content_fingerprint ---------------------------------------------------
#
# The regression this guards against: a deploy that only changes file
# CONTENT (not the file count) must still change the fingerprint, or the
# service worker's cache is never invalidated and users stay stuck on
# stale assets indefinitely.


def test_fingerprint_changes_when_a_file_s_content_changes(tmp_path):
    config = config_for(tmp_path, {"index.html": "x", "assets/app.js": "one"})
    urls = precache_urls(config)
    before = content_fingerprint(config, urls)
    (config.output / "assets/app.js").write_text("two", encoding="utf-8")
    after = content_fingerprint(config, urls)
    assert before != after


def test_fingerprint_is_stable_for_identical_content(tmp_path):
    config = config_for(tmp_path, {"index.html": "x", "assets/app.js": "same"})
    urls = precache_urls(config)
    assert content_fingerprint(config, urls) == content_fingerprint(config, urls)


def test_fingerprint_changes_when_file_count_changes(tmp_path):
    config = config_for(tmp_path, {"index.html": "x"})
    before = content_fingerprint(config, precache_urls(config))
    (config.output / "assets/app.js").parent.mkdir(parents=True, exist_ok=True)
    (config.output / "assets/app.js").write_text("new file", encoding="utf-8")
    after_urls = precache_urls(config)
    after = content_fingerprint(config, after_urls)
    assert before != after
