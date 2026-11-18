#!/usr/bin/env python3
"""KVV Abfahrten - kleiner Webserver für Home Assistant.

Fragt die (inoffizielle) EFA-Schnittstelle des KVV ab, normalisiert die
Antwort und liefert sie als JSON sowie als fertige Anzeigeseite aus.
Nur Python-Standardbibliothek, keine Abhängigkeiten.
"""
import json
import logging
import mimetypes
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

EFA_BASE = os.environ.get("KVV_EFA_BASE", "https://projekte.kvv-efa.de/sl3-alone")
OPTIONS_FILE = os.environ.get("OPTIONS_FILE", "/data/options.json")
STATIC_DIR = Path(__file__).parent / "static"
PORT = int(os.environ.get("PORT", "8099"))

# Verkehrsmittel-Codes der EFA -> lesbarer Typ
MOT_TYPES = {
    "0": "zug", "1": "sbahn", "2": "ubahn", "3": "ubahn", "4": "tram",
    "5": "bus", "6": "bus", "7": "bus", "8": "seilbahn", "9": "schiff",
    "10": "ruf", "11": "sonstige",
}

log = logging.getLogger("kvv")


def load_options():
    defaults = {
        "default_stop": "de:08212:3",
        "limit": 10,
        "cache_seconds": 30,
        "walk_minutes": 0,
        "log_level": "info",
    }
    try:
        with open(OPTIONS_FILE, encoding="utf-8") as fh:
            defaults.update(json.load(fh))
    except (OSError, ValueError):
        log.info("Keine Optionsdatei gefunden, nutze Standardwerte")
    return defaults


OPTIONS = load_options()


class TTLCache:
    """Minimaler thread-sicherer Cache, damit der KVV-Server geschont wird."""

    def __init__(self):
        self._data = {}
        self._lock = threading.Lock()

    def get(self, key, ttl):
        with self._lock:
            hit = self._data.get(key)
            if hit and time.monotonic() - hit[0] < ttl:
                return hit[1]
        return None

    def get_stale(self, key):
        with self._lock:
            hit = self._data.get(key)
            return hit[1] if hit else None

    def set(self, key, value):
        with self._lock:
            self._data[key] = (time.monotonic(), value)
            if len(self._data) > 500:  # simple Begrenzung
                oldest = min(self._data, key=lambda k: self._data[k][0])
                del self._data[oldest]


CACHE = TTLCache()


def efa_get(endpoint, params):
    query = urllib.parse.urlencode(params)
    url = f"{EFA_BASE}/{endpoint}?{query}"
    req = urllib.request.Request(url, headers={"User-Agent": "ha-kvv-departures/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _dt(d):
    """EFA-Datumsdict -> datetime (lokale Zeit) oder None."""
    if not d:
        return None
    try:
        return datetime(int(d["year"]), int(d["month"]), int(d["day"]),
                        int(d["hour"]), int(d["minute"]))
    except (KeyError, ValueError, TypeError):
        return None


def _as_list(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def normalize_departure(raw):
    line = raw.get("servingLine") or {}
    planned = _dt(raw.get("dateTime"))
    real = _dt(raw.get("realDateTime"))
    has_realtime = bool(real) and line.get("realtime") == "1"

    delay = None
    if planned and real and has_realtime:
        delay = int((real - planned).total_seconds() // 60)
    elif line.get("delay") not in (None, ""):
        try:
            delay = int(line["delay"])
        except ValueError:
            pass

    status = str(raw.get("realtimeTripStatus", ""))
    cancelled = "CANCEL" in status.upper()

    when = real if (real and has_realtime) else planned
    return {
        "line": line.get("symbol") or line.get("number") or "?",
        "direction": line.get("direction", ""),
        "type": MOT_TYPES.get(str(line.get("motType")), "sonstige"),
        "platform": raw.get("platformName") or raw.get("platform") or "",
        "stop": raw.get("nameWO") or raw.get("stopName") or "",
        "planned": planned.isoformat() if planned else None,
        "actual": when.isoformat() if when else None,
        "delay": delay,
        "realtime": has_realtime,
        "cancelled": cancelled,
        "countdown": _int(raw.get("countdown")),
    }


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def fetch_departures(stop, limit, lines=None):
    ttl = max(5, int(OPTIONS.get("cache_seconds", 30)))
    # Mehr abfragen als nötig, damit der Linienfilter genug Treffer übrig lässt
    fetch_limit = min(80, max(limit * 3, 30)) if lines else limit
    key = ("dm", stop, fetch_limit)
    data = CACHE.get(key, ttl)
    stale = False
    if data is None:
        try:
            data = efa_get("XML_DM_REQUEST", {
                "outputFormat": "JSON", "depType": "stopEvents",
                "locationServerActive": "1", "mode": "direct",
                "name_dm": stop, "type_dm": "stop",
                "useOnlyStops": "1", "useRealtime": "1",
                "limit": str(fetch_limit),
            })
            CACHE.set(key, data)
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            log.warning("KVV-Abfrage fehlgeschlagen: %s", exc)
            data = CACHE.get_stale(key)
            if data is None:
                raise
            stale = True

    points = (data.get("dm") or {}).get("points")
    if isinstance(points, list):
        # EFA liefert eine Kandidatenliste, wenn der Name nicht eindeutig ist
        raise ValueError(f"Haltestelle '{stop}' ist unbekannt oder nicht eindeutig "
                         "- bitte über die Suche eine Haltestellen-ID wählen")
    point = (points or {}).get("point")
    if isinstance(point, list):
        point = point[0] if point else {}
    stop_name = (point or {}).get("name", stop)

    deps = [normalize_departure(d) for d in _as_list(data.get("departureList"))]
    if lines:
        wanted = {l.strip().upper() for l in lines if l.strip()}
        deps = [d for d in deps if str(d["line"]).upper() in wanted]

    walk = int(OPTIONS.get("walk_minutes", 0) or 0)
    if walk > 0:
        deps = [d for d in deps if d["countdown"] is None or d["countdown"] >= walk]
    deps.sort(key=lambda d: d["actual"] or "")

    return {
        "stop": stop_name,
        "stop_id": stop,
        "updated": datetime.now().isoformat(timespec="seconds"),
        "stale": stale,
        "departures": deps[:limit],
    }


def search_stops(query):
    data = efa_get("XML_STOPFINDER_REQUEST", {
        "outputFormat": "JSON", "locationServerActive": "1",
        "type_sf": "any", "name_sf": query, "anyObjFilter_sf": "2",
    })
    points = _as_list(((data.get("stopFinder") or {}).get("points") or {}).get("point"))
    results = []
    for p in points:
        if p.get("anyType") not in (None, "stop"):
            continue
        ref = p.get("ref") or {}
        results.append({
            "id": p.get("stateless") or ref.get("id"),
            "gid": ref.get("gid"),
            "name": p.get("name"),
        })
    return [r for r in results if r["id"]]


class Handler(BaseHTTPRequestHandler):
    server_version = "KVVDepartures/1.0"

    def log_message(self, fmt, *args):
        log.debug("%s - %s", self.address_string(), fmt % args)

    def _json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        # Ingress liefert u. U. doppelte Slashes
        path = "/" + parsed.path.lstrip("/")
        qs = urllib.parse.parse_qs(parsed.query)

        try:
            if path == "/api/departures":
                stop = (qs.get("stop") or [OPTIONS["default_stop"]])[0]
                limit = max(1, min(40, int((qs.get("limit") or [OPTIONS["limit"]])[0])))
                lines = [x for v in qs.get("lines", []) for x in v.split(",")]
                return self._json(fetch_departures(stop, limit, lines))
            if path == "/api/stops":
                q = (qs.get("q") or [""])[0].strip()
                if len(q) < 2:
                    return self._json([])
                return self._json(search_stops(q))
            if path == "/api/config":
                return self._json({
                    "default_stop": OPTIONS["default_stop"],
                    "limit": OPTIONS["limit"],
                })
            if path == "/health":
                return self._json({"ok": True})
        except ValueError as exc:
            return self._json({"error": f"Ungültiger Parameter: {exc}"}, 400)
        except Exception as exc:  # noqa: BLE001
            log.exception("Fehler bei %s", path)
            return self._json({"error": f"KVV nicht erreichbar: {exc}"}, 502)

        self._static(path)

    def _static(self, path):
        rel = "index.html" if path in ("/", "") else path.lstrip("/")
        target = (STATIC_DIR / rel).resolve()
        if STATIC_DIR.resolve() not in target.parents or not target.is_file():
            self.send_error(404)
            return
        body = target.read_bytes()
        ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", f"{ctype}; charset=utf-8" if ctype.startswith("text") else ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    logging.basicConfig(
        level=getattr(logging, str(OPTIONS.get("log_level", "info")).upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(message)s",
    )
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    log.info("KVV Abfahrten läuft auf Port %d (Standard-Haltestelle: %s)",
             PORT, OPTIONS["default_stop"])
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
