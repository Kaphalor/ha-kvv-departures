"""Consistency checks between manifest, constants and shipped files."""
import json
import re
from pathlib import Path

PKG = Path(__file__).parent.parent / "custom_components/kvv_departures"


def test_versions_in_sync():
    manifest = json.loads((PKG / "manifest.json").read_text("utf-8"))["version"]
    const = re.search(r'VERSION = "([\d.]+)"', (PKG / "const.py").read_text("utf-8")).group(1)
    card = re.search(r'CARD_VERSION = "([\d.]+)"', (PKG / "frontend/kvv-departures-card.js").read_text("utf-8")).group(1)
    assert manifest == const == card


def test_card_file_served_by_integration():
    assert 'CARD_FILE = "kvv-departures-card.js"' in (PKG / "const.py").read_text("utf-8")
    assert (PKG / "frontend" / "kvv-departures-card.js").is_file()


def test_manifest_dependencies_for_card():
    manifest = json.loads((PKG / "manifest.json").read_text("utf-8"))
    assert {"http", "frontend"} <= set(manifest["dependencies"])


def test_line_colors_well_formed():
    colors = json.loads((PKG / "line_colors.json").read_text("utf-8"))
    hexre = re.compile(r"^[0-9a-f]{6}$")
    for name, v in colors.items():
        for bg, fg in (v.values() if isinstance(v, dict) else [v]):
            assert hexre.match(bg) and hexre.match(fg), name
