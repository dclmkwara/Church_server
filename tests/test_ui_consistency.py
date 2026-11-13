from fasthtml.common import to_xml

from app.frontend.dclm_admin.components.ui import active_scope_breadcrumb, page_intro


def test_page_intro_omits_scope_when_shared_shell_already_displays_it():
    duplicated = to_xml(page_intro("People", "Choose a people task.", scope_label="DCL-234-KW"))
    explicit = to_xml(page_intro("People", "Choose a people task.", scope_label="DCL-234-KW", show_scope_label=True))

    assert "DCL-234-KW" not in duplicated
    assert "DCL-234-KW" in explicit
    assert "<h1" in duplicated
    assert "<h2" not in duplicated


def test_scope_control_shows_one_current_id_and_opens_hierarchy_drawer():
    rendered = to_xml(active_scope_breadcrumb("dcl.234.kw.ilr.ile.003"))

    assert "DCL-234-KW-ILR-ILE-003" in rendered
    assert rendered.count("DCL-234-KW-ILR-ILE-003") == 2  # visible label and accessible name
    assert "DCL-234-KW-ILR</" not in rendered
    assert 'data-bs-target="#scope-drawer"' in rendered
    assert 'aria-label="Change scope. Current scope: DCL-234-KW-ILR-ILE-003"' in rendered
