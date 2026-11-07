from app.frontend.dclm_admin.routes.analytics_dashboard import _line_chart


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
    assert 'cy="195.0"' not in rendered_svg
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
    assert 'cy="195.0"' in rendered_svg
