"""Every language file must expose the same keys, and the keys used by the code must exist."""
import json
import re
from pathlib import Path

PKG = Path(__file__).parent.parent / "custom_components/kvv_departures"
FILES = sorted((PKG / "translations").glob("*.json"))


def keys(node, prefix=""):
    if isinstance(node, dict):
        for k, v in node.items():
            yield from keys(v, f"{prefix}.{k}" if prefix else k)
    else:
        yield prefix


def test_languages_present():
    assert {f.stem for f in FILES} >= {"en", "de"}


def test_same_keys_in_all_languages():
    sets = {f.stem: set(keys(json.loads(f.read_text("utf-8")))) for f in FILES}
    reference = sets["en"]
    for lang, ks in sets.items():
        assert ks == reference, f"{lang}: missing {reference - ks}, extra {ks - reference}"


def test_code_keys_exist_in_translations():
    en = json.loads((PKG / "translations/en.json").read_text("utf-8"))
    code = "".join(p.read_text("utf-8") for p in PKG.glob("*.py"))
    for key in re.findall(r'_attr_translation_key = "(\w+)"', code):
        assert key in en["entity"]["sensor"], key
    for key in re.findall(r'errors\["base"\] = "(\w+)"', code):
        assert key in en["config"]["error"] or key in en["options"]["error"], key
