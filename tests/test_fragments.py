"""Pure HTML fragment builders shared by the node pages and dossiers."""

from __future__ import annotations

from spinoza_ethics.render.fragments import chain_link_list, clean_node_excerpt, node_link_list

# --- node_link_list ------------------------------------------------------


def test_node_link_list_renders_the_empty_text_as_a_paragraph():
    assert node_link_list([], "Nothing yet.") == "<p>Nothing yet.</p>"


def test_node_link_list_escapes_the_empty_text():
    assert node_link_list([], "a & b") == "<p>a &amp; b</p>"


def test_node_link_list_renders_one_item_per_link():
    html = node_link_list([{"href": "/nodes/IP1.html", "text": "IP1", "doc": "Ethics I-II"}], "e")
    assert html == (
        '<ul class="panel-list"><li><a href="/nodes/IP1.html">IP1</a>'
        '<span class="result-doc">Ethics I-II</span></li></ul>'
    )


def test_node_link_list_deduplicates_identical_href_and_label():
    item = {"href": "/nodes/IP1.html", "text": "IP1"}
    assert node_link_list([item, dict(item)], "e").count("<li>") == 1


def test_node_link_list_falls_back_through_href_keys():
    assert 'href="/text/a.html#x"' in node_link_list([{"from": "/text/a.html#x"}], "e")


def test_node_link_list_escapes_labels():
    assert "&amp;" in node_link_list([{"href": "/a", "text": "a & b"}], "e")


def test_node_link_list_caps_at_120_rows():
    items = [{"href": f"/nodes/IP{i}.html", "text": f"IP{i}"} for i in range(200)]
    assert node_link_list(items, "e").count("<li>") == 120


# --- clean_node_excerpt --------------------------------------------------


def test_clean_excerpt_strips_bracketed_page_numbers():
    assert clean_node_excerpt("[5] God, or a substance") == "God, or a substance"


def test_clean_excerpt_collapses_whitespace():
    assert clean_node_excerpt("God,\n  or a\tsubstance") == "God, or a substance"


def test_clean_excerpt_truncates_with_an_ellipsis():
    result = clean_node_excerpt("x" * 200)
    assert len(result) == 170 and result.endswith("…")


def test_clean_excerpt_leaves_short_text_alone():
    assert clean_node_excerpt("short") == "short"


def test_clean_excerpt_handles_none():
    assert clean_node_excerpt(None) == ""


# --- chain_link_list -----------------------------------------------------


def chain_item(depth: int = 1, path=("IP1",)) -> dict:
    return {
        "href": "/nodes/IP1.html",
        "code": "IP1",
        "text": "IP1",
        "depth": depth,
        "path": list(path),
        "doc": "IP1: God exists.",
    }


def test_chain_link_list_empty_text():
    assert chain_link_list([], "No chain.", "IP2", "out") == "<p>No chain.</p>"


def test_chain_link_list_renders_the_upstream_arrow_and_root():
    html = chain_link_list([chain_item()], "e", "IP2", "out")
    assert "1 step upstream · IP2 ← IP1" in html


def test_chain_link_list_renders_the_downstream_arrow():
    html = chain_link_list([chain_item()], "e", "IP2", "in")
    assert "1 step downstream · IP2 → IP1" in html


def test_chain_link_list_pluralises_the_step_count():
    html = chain_link_list([chain_item(depth=2, path=("IP3", "IP1"))], "e", "IP2", "out")
    assert "2 steps upstream · IP2 ← IP3 ← IP1" in html


def test_chain_link_list_clamps_the_depth_custom_property():
    html = chain_link_list([chain_item(depth=12)], "e", "IP2", "out")
    assert 'style="--depth:8"' in html


def test_chain_link_list_caps_at_160_rows():
    items = [chain_item() for _ in range(200)]
    assert chain_link_list(items, "e", "IP2", "out").count("<li ") == 160
