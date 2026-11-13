from bs4 import BeautifulSoup
from fasthtml.common import to_xml

from app.frontend.dclm_admin.routes.programs import _program_setup_steps


def test_event_setup_steps_are_named_and_mark_the_current_step():
    first = BeautifulSoup(to_xml(_program_setup_steps(1)), "html.parser")
    second = BeautifulSoup(to_xml(_program_setup_steps(2)), "html.parser")

    first_root = first.select_one(".program-setup-steps")
    second_root = second.select_one(".program-setup-steps")
    assert first_root is not None and first_root.get("aria-label") == "Event setup steps"
    assert first_root.get_text(" ", strip=True) == "1 Event 2 Sessions Step 1 of 2"
    assert first.select_one('[aria-current="step"]').get_text(" ", strip=True) == "1 Event"
    assert second_root is not None
    assert second_root.get_text(" ", strip=True) == "1 Event 2 Sessions Step 2 of 2"
    assert second.select_one('[aria-current="step"]').get_text(" ", strip=True) == "2 Sessions"
