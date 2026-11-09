from app.frontend.dclm_admin.routes.analytics_dashboard import _line_chart, _location_history_table, _period_delta, _scope_dashboard_link, _waiting_on_decision
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit


def test_missing_weeks_break_the_population_line_instead_of_becoming_zero():
    chart = _line_chart(
        [
            {"date": "2026-10-11", "average": None, "counted": 0, "expected": 1},
            {"date": "2026-10-18", "average": None, "counted": 0, "expected": 1},
            {"date": "2026-10-25", "average": None, "counted": 0, "expected": 1},
            {"date": "2026-11-01", "average": 166, "counted": 1, "expected": 1},
        ],
        4,
    )

    rendered_svg = str(chart.children[0])
    assert chart.attrs["data-points"] == ""
    assert "<polyline" not in rendered_svg
    assert 'cy="180.0"' not in rendered_svg
    assert rendered_svg.count("<circle") == 1


def test_an_approved_zero_is_plotted_as_zero_and_adjacent_weeks_connect():
    chart = _line_chart(
        [
            {"date": "2026-10-25", "average": 0, "counted": 1, "expected": 1},
            {"date": "2026-11-01", "average": 20, "counted": 1, "expected": 1},
        ],
        4,
    )

    rendered_svg = str(chart.children[0])
    assert chart.attrs["data-points"]
    assert '<polyline points="' in rendered_svg
    assert 'cy="180.0"' in rendered_svg


def test_population_points_bars_and_week_labels_share_the_same_x_centres():
    chart = _line_chart(
        [
            {"date": "2026-10-25", "average": 100, "counted": 1, "expected": 4},
            {"date": "2026-11-01", "average": 120, "counted": 3, "expected": 4},
        ],
        4,
    )
    rendered_svg = str(chart.children[0])

    point_x = 'cx="253.5"' in rendered_svg
    first_bar_x = 'x="155.8"' in rendered_svg
    first_label_x = 'x="253.5" y="330"' in rendered_svg
    assert point_x and first_bar_x and first_label_x
    assert "100%" in rendered_svg and "50%" in rendered_svg and "0%" in rendered_svg
    assert 'data-share="25.0"' in rendered_svg


def test_dashboard_link_preserves_scope_period_pending_and_weeks():
    from urllib.parse import urlencode

    def url_for(path, **overrides):
        return f"{path}?{urlencode(overrides)}" if overrides else path

    ctx = SimpleNamespace(
        url_for=url_for,
        current_scope_path="org.234.kw.region",
        query_extras={
            "scope_path": "org.234.kw.region",
            "period": "quarter",
            "include_pending": "true",
            "weeks": "8",
        },
    )

    full_url = _scope_dashboard_link(ctx, "org.234.kw.region.group")
    htmx_url = _scope_dashboard_link(ctx, "org.234.kw.region.group", fragment=True)
    query = parse_qs(urlsplit(full_url).query)

    assert urlsplit(full_url).path == "/dashboard"
    assert urlsplit(htmx_url).path == "/dashboard/content"
    assert query == {
        "scope_path": ["org.234.kw.region.group"],
        "period": ["quarter"],
        "include_pending": ["true"],
        "weeks": ["8"],
    }


def test_location_history_keeps_missing_zero_pending_and_combined_distinct():
    from datetime import date

    history = [
        {"total": None, "coverage": {"approved": 0, "pending": 0, "returned": 0, "missing": 1}},
        {"total": 0, "coverage": {"approved": 1, "pending": 0, "returned": 0, "combined": 0}},
        {"total": None, "coverage": {"approved": 1, "pending": 0, "returned": 0, "combined": 1}},
        {"total": None, "coverage": {"approved": 0, "pending": 1, "returned": 0, "combined": 0}},
    ]
    table = _location_history_table(history, [date(2026, 10, 11) + __import__("datetime").timedelta(weeks=i) for i in range(4)])
    rendered = str(table)

    assert "Not reported" in rendered
    assert "Reported 0" in rendered
    assert "Included in combined report" in rendered
    assert "No separate location total" in rendered
    assert "Awaiting approval" in rendered


def test_dashboard_period_delta_handles_zero_and_no_comparison_without_nan():
    assert _period_delta(120, 100, previous_records=2, noun="4 Sundays") == "Up 20% vs previous 4 Sundays"
    assert _period_delta(0, 100, previous_records=1, noun="4 Sundays") == "Down 100% vs previous 4 Sundays"
    assert _period_delta(10, 0, previous_records=0, noun="4 Sundays") == "New this period · 4 Sundays"
    assert _period_delta(0, 0, previous_records=0, noun="4 Sundays") == "No prior-period records to compare"


def test_waiting_on_decision_shows_category_count_and_oldest_age():
    panel = _waiting_on_decision({"pending_approvals": [{"label": "Count reports", "count": 3, "oldest_age_hours": 26}]}, 4)
    rendered = str(panel)
    assert "Waiting on a decision" in rendered
    assert "Count reports" in rendered and "3" in rendered and "oldest waiting 26h" in rendered
    empty = str(_waiting_on_decision({"pending_approvals": []}, 8))
    assert "No requests waiting for a decision." in empty
