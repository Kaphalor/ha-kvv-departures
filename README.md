# KVV Departures for Home Assistant

A native Home Assistant integration (HACS compatible) that shows live departures,
delays and cancellations for any stop in the network of the Karlsruher
Verkehrsverbund (KVV), as regular sensors. No iframe and no add-on required.

The UI follows each user's display language. German and English are included;
Home Assistant picks the translation per user, so every household member sees
the setup dialogs and entity names in their own language.

## Installation

**HACS (recommended)**

1. HACS → ⋮ → *Custom repositories* → add `https://github.com/Kaphalor/ha-kvv-departures` as type *Integration*.
2. Install *KVV Departures* and restart Home Assistant.

**Manual**

1. Copy `custom_components/kvv_departures` to `<config>/custom_components/`.
2. Restart Home Assistant.

Then go to *Settings → Devices & services → Add integration → KVV Departures*,
search for a stop and select it. Add the integration again for each additional stop.

Settings (gear icon on the entry): number of departures, line filter, walking
time in minutes, update interval and data source.

## Entities per stop

| Entity | Content |
|---|---|
| Next departure | Timestamp of the next departure (actual time). The attribute `departures` holds the complete list. |
| Delay of next departure | Delay in minutes. |
| Departure 1 … N | One entity per departure. Attributes: `line`, `direction`, `platform`, `delay`, `planned_time`, `time`, `cancelled`, `text`. |

Entity IDs are generated from the entity names in Home Assistant's system
language when the entity is first created, for example
`sensor.durlacher_tor_next_departure` (English) or
`sensor.durlacher_tor_nachste_abfahrt` (German). Check the exact IDs under
*Devices & services → KVV Departures*.

## Dashboard

**Markdown card** with delays:

```yaml
type: markdown
title: Durlacher Tor
content: >
  {% set deps = state_attr('sensor.durlacher_tor_next_departure', 'departures') or [] %}
  {% for d in deps %}
  **{{ d.line }}** {{ d.direction }} – **{{ d.time }}**
  {%- if d.cancelled %} ❌ cancelled
  {%- elif d.delay and d.delay > 0 %} (+{{ d.delay }} min, scheduled {{ d.planned_time }})
  {%- endif %}

  {% endfor %}
```

The text inside a card template is your own, so write it in whichever
language you like.

**Entities card** using the single-departure sensors:

```yaml
type: entities
entities:
  - entity: sensor.durlacher_tor_departure_1
    secondary_info: attribute
    attribute: text
  - entity: sensor.durlacher_tor_departure_2
  - entity: sensor.durlacher_tor_departure_3
```

## Data sources

| Source | Status |
|---|---|
| `efa` (default) | Unofficial EFA interface at `projekte.kvv-efa.de`. No registration, real-time data. Undocumented and may change without notice. |
| `trias` | Official [KVV open data interface](https://www.kvv.de/fahrplan/fahrplaene/open-data.html) (VDV 431-2). Access requires a usage agreement; contact fahrplan@kvv.karlsruhe.de. |

To use TRIAS, set the source to `trias` in the settings and enter the URL and
requestor reference you receive from KVV. Stop search always uses EFA.

**The TRIAS client has only been tested against a hand-written sample response,
not against the real server.** Expect small adjustments (authentication,
namespaces, stop IDs) once you have real credentials.

## Status

The API layer is covered by automated tests, including live requests to KVV. The
Home Assistant parts (config flow, sensors, translations) have been syntax-checked
but not yet run in a real Home Assistant instance.

## Development

```
python -m venv venv && venv/bin/pip install aiohttp pytest pytest-asyncio
venv/bin/pytest tests
```

Translations live in `custom_components/kvv_departures/translations/`. To add a
language, copy `en.json` to `<language code>.json` and translate the values;
`tests/test_translations.py` checks that all languages have the same keys.

## Disclaimer

This is an unofficial project and is not affiliated with the KVV.
