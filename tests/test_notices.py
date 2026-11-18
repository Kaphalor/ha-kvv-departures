"""Notice links: the EFA content endpoint answers 403 to everyone, so it must not be linked."""
import importlib.util
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "kvv_api", Path(__file__).parent.parent / "custom_components/kvv_departures/api.py")
api = sys.modules.get("kvv_api") or importlib.util.module_from_spec(spec)
if "kvv_api" not in sys.modules:
    sys.modules["kvv_api"] = api
    spec.loader.exec_module(api)

DEAD = ("http://projekte.kvv-efa.de:80/cm/XSLT_CM_SHOWADDINFO_REQUEST"
        "?infoID=100004526_KVV_ICSKVV&seqID=4")


def test_dead_notice_link_dropped_text_kept():
    infos = api._efa_infos({"lineInfo": {
        "infoText": {"subtitle": "Karlsruhe: Bauarbeiten im VBK-Netz (Phase 5)"},
        "infoLinkURL": DEAD}})
    assert infos == (("Karlsruhe: Bauarbeiten im VBK-Netz (Phase 5)", ""),)


def test_other_links_are_kept():
    infos = api._efa_infos({"lineInfo": [
        {"infoText": {"subtitle": "A"}, "infoLinkURL": "https://example.org/a"},
        {"infoText": {"subtitle": "B"}, "infoLinkURL": DEAD}]})
    assert infos == (("A", "https://example.org/a"), ("B", ""))
