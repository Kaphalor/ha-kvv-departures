"""Tests für api.py (ohne Home Assistant). Ausführen: pytest tests"""
import importlib.util
import sys
from datetime import datetime, timedelta
from pathlib import Path

import aiohttp
import pytest

spec = importlib.util.spec_from_file_location(
    "kvv_api", Path(__file__).parent.parent / "custom_components/kvv_departures/api.py")
api = importlib.util.module_from_spec(spec)
sys.modules["kvv_api"] = api  # dataclasses brauchen das Modul in sys.modules
spec.loader.exec_module(api)

TRIAS_SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<Trias xmlns="http://www.vdv.de/trias" xmlns:siri="http://www.siri.org.uk/siri" version="1.1">
 <ServiceDelivery><DeliveryPayload><StopEventResponse><StopEventResult>
  <StopEvent><ThisCall><CallAtStop>
    <StopPointRef>de:08212:3</StopPointRef>
    <PlannedBay><Text>Gleis 4</Text></PlannedBay>
    <ServiceDeparture>
      <TimetabledTime>2026-11-18T07:23:00Z</TimetabledTime>
      <EstimatedTime>2026-11-18T07:28:00Z</EstimatedTime>
    </ServiceDeparture></CallAtStop></ThisCall>
    <Service><Mode><PtMode>tram</PtMode></Mode>
      <PublishedLineName><Text>3</Text></PublishedLineName>
      <DestinationText><Text>Rintheim</Text></DestinationText></Service>
  </StopEvent>
  <StopEvent><ThisCall><CallAtStop>
    <ServiceDeparture><TimetabledTime>2026-11-18T07:20:00Z</TimetabledTime></ServiceDeparture>
    </CallAtStop></ThisCall>
    <Service><Mode><PtMode>urbanRail</PtMode></Mode><Cancelled>true</Cancelled>
      <PublishedLineName><Text>S5</Text></PublishedLineName>
      <DestinationText><Text>Knielingen</Text></DestinationText></Service>
  </StopEvent>
 </StopEventResult></StopEventResponse></DeliveryPayload></ServiceDelivery></Trias>"""


def test_trias_parse():
    deps = api.parse_trias_departures(TRIAS_SAMPLE)
    assert [d.line for d in deps] == ["S5", "3"]  # nach Ist-Zeit sortiert
    s5, tram = deps
    assert s5.cancelled and s5.delay is None and not s5.realtime and s5.mode == "sbahn"
    assert tram.delay == 5 and tram.realtime and tram.mode == "tram"
    assert tram.platform == "Gleis 4" and tram.direction == "Rintheim"
    assert tram.actual.strftime("%H:%M") == "08:28"  # 07:28Z = 08:28 Berlin (Winterzeit)


def test_trias_error():
    xml = ('<Trias xmlns="http://www.vdv.de/trias"><ErrorMessage><Text><Text>kaputt</Text></Text>'
           '</ErrorMessage></Trias>')
    with pytest.raises(api.KvvError):
        api.parse_trias_departures(xml)


def test_trias_request_escapes():
    client = api.TriasClient(None, "https://x", 'a<b&"')
    xml = client.build_request(api.Stop("1", "de:1", "X"), 3,
                               datetime(2026, 11, 18, 8, 0, tzinfo=api.TZ))
    assert "a&lt;b&amp;" in xml and "<NumberOfResults>3</NumberOfResults>" in xml
    import xml.etree.ElementTree as ET
    ET.fromstring(xml)  # wohlgeformt


def _dep(line, minutes, now):
    t = now + timedelta(minutes=minutes)
    return api.Departure(line, "X", "tram", "", t, t, 0, True, False)


def test_filters():
    now = datetime(2026, 11, 18, 8, 0, tzinfo=api.TZ)
    deps = [_dep("S1", 1, now), _dep("3", 5, now), _dep("S5", 9, now), _dep("S1", 12, now)]
    assert api.parse_lines("s1; 3 ,") == {"S1", "3"}
    out = api.filter_departures(deps, {"S1", "3"}, 4, now, 5)
    assert [(d.line, int((d.actual - now).total_seconds() // 60)) for d in out] == [("3", 5), ("S1", 12)]
    assert len(api.filter_departures(deps, set(), 0, now, 2)) == 2


def test_efa_parse_delay():
    raw = {"dateTime": dict(year="2026", month="11", day="18", hour="8", minute="23"),
           "realDateTime": dict(year="2026", month="11", day="18", hour="8", minute="29"),
           "servingLine": {"symbol": "3", "motType": "4", "realtime": "1", "direction": "Rintheim"},
           "realtimeTripStatus": "MONITORED", "platformName": "Gleis 4"}
    d = api.parse_efa_departure(raw)
    assert d.delay == 6 and d.realtime and d.mode == "tram" and not d.cancelled
    raw["realtimeTripStatus"] = "TRIP_CANCELLED"
    assert api.parse_efa_departure(raw).cancelled


@pytest.mark.asyncio
async def test_efa_live():
    async with aiohttp.ClientSession() as s:
        client = api.EfaClient(s)
        stops = await client.search_stops("Durlach")
        assert len(stops) > 1 and all(x.id for x in stops)
        marktplatz = (await client.search_stops("Marktplatz"))[0]
        deps = await client.departures(marktplatz, 5)
        assert deps and all(d.actual >= d.planned or d.delay is not None for d in deps)
        with pytest.raises(api.KvvStopError):
            await client.departures(api.Stop("gibtsnicht", "", "x"), 3)
