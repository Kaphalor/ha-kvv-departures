"""API clients for KVV departures: EFA (unofficial) and TRIAS (official)."""
from __future__ import annotations

import asyncio
import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

import aiohttp

TZ = ZoneInfo("Europe/Berlin")
EFA_BASE = "https://projekte.kvv-efa.de/sl3-alone"
TIMEOUT = aiohttp.ClientTimeout(total=20)

# EFA motType -> internal type
_EFA_MOT = {
    "0": "zug", "1": "sbahn", "2": "ubahn", "3": "ubahn", "4": "tram",
    "5": "bus", "6": "bus", "7": "bus", "8": "seilbahn", "9": "schiff",
}
# TRIAS PtMode -> internal type
_TRIAS_MODE = {
    "rail": "zug", "urbanRail": "sbahn", "metro": "ubahn", "tram": "tram",
    "bus": "bus", "coach": "bus", "trolleyBus": "bus", "water": "schiff",
    "cableway": "seilbahn", "funicular": "seilbahn",
}


class KvvError(Exception):
    """Generic request error."""


class KvvAuthError(KvvError):
    """Credentials rejected (TRIAS)."""


class KvvStopError(KvvError):
    """Stop unknown or ambiguous."""


@dataclass(frozen=True)
class Stop:
    id: str
    gid: str
    name: str


# Official line colors from the KVV GTFS feed (CC0), see scripts/generate_line_colors.py.
# Loaded at import time: Home Assistant imports integrations in an executor,
# so this does not block the event loop.
_COLORS: dict[str, Any] = json.loads(
    Path(__file__).with_name("line_colors.json").read_text(encoding="utf-8"))
# internal mode -> GTFS route_type, only used to resolve ambiguous names (e.g. "E")
_GTFS_TYPE = {"tram": "0", "ubahn": "0", "sbahn": "2", "zug": "2", "bus": "3"}
_FALLBACK_COLOR = {"tram": "e30613", "sbahn": "00975f", "ubahn": "0a6fb7",
                   "zug": "1f3a93", "bus": "91268f"}


def line_color(line: str, mode: str) -> tuple[str, str]:
    """Return (background, text) as '#rrggbb' for a line, using the official colors."""
    entry = _COLORS.get(line.strip().upper())
    if isinstance(entry, dict):
        entry = entry.get(_GTFS_TYPE.get(mode, ""), next(iter(entry.values())))
    if entry:
        return f"#{entry[0]}", f"#{entry[1]}"
    return f"#{_FALLBACK_COLOR.get(mode, '5b6573')}", "#ffffff"


@dataclass(frozen=True)
class Departure:
    line: str
    direction: str
    mode: str
    platform: str
    planned: datetime
    actual: datetime
    delay: int | None
    realtime: bool
    cancelled: bool
    stop: str = ""
    operator: str = ""
    infos: tuple[tuple[str, str], ...] = ()  # (title, url)

    def as_dict(self) -> dict[str, Any]:
        color, text_color = line_color(self.line, self.mode)
        return {
            "line": self.line,
            "direction": self.direction,
            "mode": self.mode,
            "platform": self.platform,
            "stop": self.stop,
            "operator": self.operator,
            "color": color,
            "text_color": text_color,
            "planned": self.planned.isoformat(),
            "actual": self.actual.isoformat(),
            "time": self.actual.strftime("%H:%M"),
            "planned_time": self.planned.strftime("%H:%M"),
            "delay": self.delay,
            "realtime": self.realtime,
            "cancelled": self.cancelled,
            "infos": [{"title": t, "url": u} for t, u in self.infos],
        }


def _as_list(value: Any) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


# --------------------------------------------------------------------- EFA
def _efa_dt(d: dict | None) -> datetime | None:
    if not d:
        return None
    try:
        return datetime(int(d["year"]), int(d["month"]), int(d["day"]),
                        int(d["hour"]), int(d["minute"]), tzinfo=TZ)
    except (KeyError, ValueError, TypeError):
        return None


def parse_efa_departure(raw: dict) -> Departure | None:
    line = raw.get("servingLine") or {}
    planned = _efa_dt(raw.get("dateTime"))
    if planned is None:
        return None
    real = _efa_dt(raw.get("realDateTime"))
    has_rt = real is not None and line.get("realtime") == "1"
    actual = real if has_rt else planned

    delay: int | None = None
    if has_rt:
        delay = int((actual - planned).total_seconds() // 60)
    elif line.get("delay") not in (None, ""):
        try:
            delay = int(line["delay"])
        except ValueError:
            pass

    return Departure(
        line=str(line.get("symbol") or line.get("number") or "?"),
        direction=line.get("direction", ""),
        mode=_EFA_MOT.get(str(line.get("motType")), "sonstige"),
        platform=raw.get("platformName") or raw.get("platform") or "",
        planned=planned,
        actual=actual,
        delay=delay,
        realtime=has_rt,
        cancelled="CANCEL" in str(raw.get("realtimeTripStatus", "")).upper(),
        stop=raw.get("nameWO") or raw.get("stopName") or "",
        operator=(raw.get("operator") or {}).get("name", ""),
        infos=_efa_infos(raw.get("lineInfos")),
    )


def _efa_infos(line_infos: Any) -> tuple[tuple[str, str], ...]:
    """Disruption/construction notices attached to a departure (max. 3)."""
    if not isinstance(line_infos, dict):
        return ()
    out = []
    for info in _as_list(line_infos.get("lineInfo")):
        text = info.get("infoText") or {}
        title = (text.get("subtitle") or info.get("infoLinkText") or "").strip()
        if title:
            out.append((title, info.get("infoLinkURL") or ""))
    return tuple(out[:3])


class EfaClient:
    """Unofficial EFA interface (no login required)."""

    def __init__(self, session: aiohttp.ClientSession, base: str = EFA_BASE) -> None:
        self._session = session
        self._base = base

    async def _get(self, endpoint: str, params: dict[str, str]) -> dict:
        try:
            async with self._session.get(
                f"{self._base}/{endpoint}", params=params, timeout=TIMEOUT,
                headers={"User-Agent": "ha-kvv-departures"},
            ) as resp:
                resp.raise_for_status()
                return await resp.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as err:
            raise KvvError(f"KVV EFA unreachable: {err}") from err

    async def search_stops(self, query: str) -> list[Stop]:
        data = await self._get("XML_STOPFINDER_REQUEST", {
            "outputFormat": "JSON", "locationServerActive": "1",
            "type_sf": "any", "name_sf": query, "anyObjFilter_sf": "2",
        })
        points = ((data.get("stopFinder") or {}).get("points") or {})
        if isinstance(points, dict):
            points = points.get("point")
        stops = []
        for p in _as_list(points):
            if p.get("anyType") not in (None, "stop"):
                continue
            ref = p.get("ref") or {}
            sid = p.get("stateless") or ref.get("id")
            if sid:
                stops.append(Stop(str(sid), ref.get("gid") or "", p.get("name", sid)))
        return stops

    async def departures(self, stop: Stop, limit: int) -> list[Departure]:
        data = await self._get("XML_DM_REQUEST", {
            "outputFormat": "JSON", "depType": "stopEvents",
            "locationServerActive": "1", "mode": "direct",
            "name_dm": stop.id, "type_dm": "stop",
            "useOnlyStops": "1", "useRealtime": "1", "limit": str(limit),
        })
        points = (data.get("dm") or {}).get("points")
        if points is None or isinstance(points, list):
            # No match at all (null) or a candidate list: unknown or ambiguous
            raise KvvStopError(f"Stop {stop.id} unknown or ambiguous")
        deps = [parse_efa_departure(d) for d in _as_list(data.get("departureList"))]
        return sorted((d for d in deps if d), key=lambda d: d.actual)


# ---------------------------------------------------------------- Filter



def parse_lines(value: str | None) -> set[str]:
    return {p.strip().upper() for p in (value or "").replace(";", ",").split(",") if p.strip()}


def filter_departures(deps: list[Departure], lines: set[str], walk: int,
                      now: datetime, count: int) -> list[Departure]:
    if lines:
        deps = [d for d in deps if d.line.upper() in lines]
    if walk > 0:
        deps = [d for d in deps if d.actual >= now + timedelta(minutes=walk)]
    return deps[:count]


# ------------------------------------------------------------------- TRIAS
def _children(el: ET.Element, name: str) -> list[ET.Element]:
    return [c for c in el if c.tag.rsplit("}", 1)[-1] == name]


def _path(el: ET.Element | None, *names: str) -> ET.Element | None:
    for name in names:
        if el is None:
            return None
        found = _children(el, name)
        el = found[0] if found else None
    return el


def _text(el: ET.Element | None, *names: str) -> str:
    node = _path(el, *names)
    return (node.text or "").strip() if node is not None else ""


def _iso(value: str) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt.astimezone(TZ) if dt.tzinfo else dt.replace(tzinfo=TZ)


def parse_trias_departures(xml_text: str) -> list[Departure]:
    """Convert a TRIAS StopEventResponse into departures."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as err:
        raise KvvError(f"Invalid TRIAS response: {err}") from err

    for err_el in root.iter():
        if err_el.tag.rsplit("}", 1)[-1] == "ErrorMessage":
            msg = _text(err_el, "Text", "Text") or _text(err_el, "Text") or "unknown"
            raise KvvError(f"TRIAS error: {msg}")

    result: list[Departure] = []
    for ev in (e for e in root.iter() if e.tag.rsplit("}", 1)[-1] == "StopEvent"):
        call = _path(ev, "ThisCall", "CallAtStop")
        service = _path(ev, "Service")
        dep = _path(call, "ServiceDeparture")
        planned = _iso(_text(dep, "TimetabledTime"))
        if planned is None:
            continue
        estimated = _iso(_text(dep, "EstimatedTime"))
        actual = estimated or planned
        cancelled = (_text(service, "Cancelled").lower() == "true"
                     or _text(call, "NotServicedStop").lower() == "true")
        result.append(Departure(
            line=_text(service, "PublishedLineName", "Text") or _text(service, "ServiceSection", "PublishedLineName", "Text") or "?",
            direction=_text(service, "DestinationText", "Text"),
            mode=_TRIAS_MODE.get(_text(service, "Mode", "PtMode"), "sonstige"),
            platform=_text(call, "EstimatedBay", "Text") or _text(call, "PlannedBay", "Text"),
            planned=planned,
            actual=actual,
            delay=int((actual - planned).total_seconds() // 60) if estimated else None,
            realtime=estimated is not None,
            cancelled=cancelled,
            stop=_text(call, "StopPointName", "Text"),
        ))
    return sorted(result, key=lambda d: d.actual)


class TriasClient:
    """Official TRIAS interface (requires access granted by KVV)."""

    def __init__(self, session: aiohttp.ClientSession, url: str, requestor_ref: str) -> None:
        self._session = session
        self._url = url
        self._ref = requestor_ref

    def build_request(self, stop: Stop, limit: int, now: datetime | None = None) -> str:
        now = now or datetime.now(TZ)
        ts = now.astimezone(TZ).isoformat(timespec="seconds")
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<Trias version="1.1" xmlns="http://www.vdv.de/trias" xmlns:siri="http://www.siri.org.uk/siri">
  <ServiceRequest>
    <siri:RequestTimestamp>{ts}</siri:RequestTimestamp>
    <siri:RequestorRef>{escape(self._ref)}</siri:RequestorRef>
    <RequestPayload>
      <StopEventRequest>
        <Location>
          <LocationRef><StopPointRef>{escape(stop.gid or stop.id)}</StopPointRef></LocationRef>
          <DepArrTime>{ts}</DepArrTime>
        </Location>
        <Params>
          <NumberOfResults>{int(limit)}</NumberOfResults>
          <StopEventType>departure</StopEventType>
          <IncludeRealtimeData>true</IncludeRealtimeData>
        </Params>
      </StopEventRequest>
    </RequestPayload>
  </ServiceRequest>
</Trias>"""

    async def departures(self, stop: Stop, limit: int) -> list[Departure]:
        try:
            async with self._session.post(
                self._url, data=self.build_request(stop, limit).encode("utf-8"),
                headers={"Content-Type": "text/xml; charset=utf-8"}, timeout=TIMEOUT,
            ) as resp:
                if resp.status in (401, 403):
                    raise KvvAuthError("TRIAS access denied")
                resp.raise_for_status()
                text = await resp.text()
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise KvvError(f"TRIAS unreachable: {err}") from err
        return parse_trias_departures(text)
