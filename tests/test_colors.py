"""Line colors and departure details (no Home Assistant needed)."""
import importlib.util
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "kvv_api", Path(__file__).parent.parent / "custom_components/kvv_departures/api.py")
api = sys.modules.get("kvv_api") or importlib.util.module_from_spec(spec)
if "kvv_api" not in sys.modules:
    sys.modules["kvv_api"] = api
    spec.loader.exec_module(api)


def test_line_colors_official():
    assert api.line_color("1", "tram") == ("#e30613", "#ffffff")
    assert api.line_color("4", "tram") == ("#ffcc00", "#000000")  # yellow with black text
    assert api.line_color("s5", "sbahn")[0] == "#f39b9a"           # case-insensitive
    # ambiguous name "E": tram (red) vs. rail (green)
    assert api.line_color("E", "tram")[0] == "#e30613"
    assert api.line_color("E", "sbahn")[0] == "#00975f"
    # unknown line -> neutral fallback by mode, never an exception
    assert api.line_color("ZZZ99", "bus") == ("#91268f", "#ffffff")
    assert api.line_color("ZZZ99", "sonstige") == ("#5b6573", "#ffffff")


def test_efa_details_and_color_in_dict():
    raw = {"dateTime": dict(year="2026", month="11", day="18", hour="8", minute="23"),
           "realDateTime": dict(year="2026", month="11", day="18", hour="8", minute="29"),
           "servingLine": {"symbol": "3", "motType": "4", "realtime": "1", "direction": "Rintheim"},
           "nameWO": "Durlacher Tor/KIT-Campus Süd", "operator": {"name": "VBK"},
           "lineInfos": {"lineInfo": [{"infoText": {"subtitle": "Bauarbeiten"}, "infoLinkURL": "http://x/y"},
                                      {"infoLinkText": "Nur Text"}]}}
    out = api.parse_efa_departure(raw).as_dict()
    assert out["color"] == "#966c29" and out["text_color"] == "#ffffff"
    assert out["stop"].startswith("Durlacher Tor") and out["operator"] == "VBK"
    assert out["infos"] == [{"title": "Bauarbeiten", "url": "http://x/y"}, {"title": "Nur Text", "url": ""}]
    # a single lineInfo object (not a list) must work too
    raw["lineInfos"] = {"lineInfo": {"infoText": {"subtitle": "Einzeln"}}}
    assert api.parse_efa_departure(raw).infos == (("Einzeln", ""),)
    raw["lineInfos"] = None
    assert api.parse_efa_departure(raw).infos == ()
