from pathlib import Path


def test_first_party_admin_frontend_sources_contain_no_mojibake_markers():
    root = Path(__file__).parents[1] / "app" / "frontend" / "dclm_admin"
    markers = (
        chr(0x00C3),  # common UTF-8 decoded as Latin-1
        chr(0x00C2),
        chr(0x00E2) + chr(0x20AC),
        chr(0xFFFD),
    )
    offenders = []
    for path in root.rglob("*"):
        if path.suffix not in {".py", ".html", ".js", ".css"} or path.name == "chart.umd.min.js":
            continue
        text = path.read_text(encoding="utf-8-sig")
        if any(marker in text for marker in markers):
            offenders.append(path.relative_to(root).as_posix())
    assert not offenders, "Mojibake markers found in: " + ", ".join(offenders)
