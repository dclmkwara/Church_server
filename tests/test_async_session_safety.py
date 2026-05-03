from pathlib import Path


def test_request_db_code_does_not_gather_on_shared_async_session():
    root = Path(__file__).resolve().parents[1] / "app"
    checked_dirs = [
        root / "services",
        root / "api" / "v1" / "routes",
    ]
    offenders = []
    for directory in checked_dirs:
        for path in directory.glob("*.py"):
            text = path.read_text(encoding="utf-8")
            if "asyncio.gather(" in text:
                offenders.append(str(path.relative_to(root.parent)))

    assert offenders == []
