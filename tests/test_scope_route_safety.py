from pathlib import Path


def test_routes_do_not_use_requested_scope_directly():
    route_dir = Path(__file__).resolve().parents[1] / "app" / "api" / "v1" / "routes"
    unsafe_patterns = [
        "scope_path if scope_path else",
        "search_scope = scope_path",
    ]
    offenders = []
    for path in route_dir.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for pattern in unsafe_patterns:
            if pattern in text:
                offenders.append(f"{path.name}: {pattern}")

    assert offenders == []
