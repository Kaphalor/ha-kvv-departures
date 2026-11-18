#!/usr/bin/env python3
"""Generate custom_components/kvv_departures/line_colors.json from the KVV GTFS feed.

The feed is published by KVV under CC0:
    https://projekte.kvv-efa.de/GTFS/google_transit.zip

Usage:
    python3 scripts/generate_line_colors.py path/to/google_transit.zip

Only routes.txt is read from the archive; nothing is extracted or executed.
Output format: {"<LINE>": ["rrggbb", "rrggbb text"]}. When the same line name
exists with different colors (e.g. tram "E" vs. rail "E"), the value is a dict
keyed by GTFS route_type ("0" tram, "2" rail, "3" bus) instead.
"""
import csv
import io
import json
import sys
import zipfile
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "custom_components/kvv_departures/line_colors.json"


def main(zip_path: str) -> None:
    with zipfile.ZipFile(zip_path) as zf:
        text = zf.read("routes.txt").decode("utf-8-sig")
    variants: dict[str, dict[str, list[str]]] = {}
    for row in csv.DictReader(io.StringIO(text)):
        name = row["route_short_name"].strip().upper()
        color, text_color = row["route_color"].strip().lower(), row["route_text_color"].strip().lower()
        if not name or not color:
            continue
        variants.setdefault(name, {})[row["route_type"]] = [color, text_color or "ffffff"]

    result: dict[str, object] = {}
    for name in sorted(variants):
        by_type = variants[name]
        distinct = {tuple(v) for v in by_type.values()}
        result[name] = next(iter(by_type.values())) if len(distinct) == 1 else by_type
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=0, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({len(result)} lines, {sum(isinstance(v, dict) for v in result.values())} ambiguous)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
