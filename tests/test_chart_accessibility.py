from fasthtml.common import to_xml

from app.frontend.dclm_admin.components.chartjs import bar_chart, donut_chart, sparkline_chart


def test_sparkline_has_named_canvas_and_expandable_data_table():
    rendered = to_xml(sparkline_chart([("Sun 1", 12), ("Sun 2", 19)], stroke="#123456", fill="#abcdef", label="Attendance"))

    assert 'role="img"' in rendered
    assert 'aria-label="Attendance"' in rendered
    assert "View chart data" in rendered
    assert "Sun 1" in rendered and "12" in rendered
    assert "Sun 2" in rendered and "19" in rendered


def test_donut_and_bar_charts_include_the_values_used_to_draw_them():
    donut = to_xml(donut_chart([{"label": "Approved", "value": 8}, {"label": "Waiting", "value": 2}], label="Reports", total_label="Total"))
    bars = to_xml(bar_chart([{"label": "Location A", "value": 7}], label="Attendance"))

    assert "Approved" in donut and "Waiting" in donut and "8" in donut and "2" in donut
    assert "Location A" in bars and "7" in bars
