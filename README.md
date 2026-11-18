# KVV Abfahrten für Home Assistant

Native Integration (HACS-fähig): Abfahrten inkl. Verspätung und Ausfällen für
jede Haltestelle im KVV-Netz als normale Sensoren. Kein iframe, kein Addon nötig.

> Der Ordner `kvv_departures/` und `repository.yaml` gehören zum früheren
> Addon-Entwurf und werden nicht mehr gebraucht.

## Installation

1. Ordner `custom_components/kvv_departures` nach `<config>/custom_components/` kopieren
   (oder dieses Repo in HACS als *Benutzerdefiniertes Repository* → Integration hinzufügen).
2. Home Assistant neu starten.
3. *Einstellungen → Geräte & Dienste → Integration hinzufügen → KVV Abfahrten*,
   Haltestelle suchen und auswählen. Pro Haltestelle ein Eintrag.

Einstellungen (Zahnrad am Eintrag): Anzahl Abfahrten, Linienfilter, Fußweg in
Minuten, Aktualisierungsintervall, Datenquelle.

## Entitäten pro Haltestelle

| Entität | Inhalt |
|---|---|
| `sensor.<haltestelle>_nachste_abfahrt` | Zeitstempel der nächsten Abfahrt (Ist-Zeit); Attribut `departures` = komplette Liste |
| `sensor.<haltestelle>_verspatung_nachste_abfahrt` | Verspätung in Minuten |
| `sensor.<haltestelle>_abfahrt_1` … `_N` | je eine Abfahrt: Attribute `line`, `direction`, `platform`, `delay`, `planned_time`, `time`, `cancelled`, `text` |

## Dashboard (nativ)

**Markdown-Karte** mit Verspätungen:

```yaml
type: markdown
title: Durlacher Tor
content: >
  {% set deps = state_attr('sensor.durlacher_tor_nachste_abfahrt', 'departures') or [] %}
  {% for d in deps %}
  **{{ d.line }}** {{ d.direction }} – **{{ d.time }}**
  {%- if d.cancelled %} ❌ fällt aus
  {%- elif d.delay and d.delay > 0 %} (+{{ d.delay }} min, planmäßig {{ d.planned_time }})
  {%- endif %}

  {% endfor %}
```

**Entities-Karte** mit den Einzel-Sensoren:

```yaml
type: entities
entities:
  - entity: sensor.durlacher_tor_abfahrt_1
    secondary_info: attribute
    attribute: text
  - entity: sensor.durlacher_tor_abfahrt_2
  - entity: sensor.durlacher_tor_abfahrt_3
```

Die genauen Entitäts-IDs stehen unter *Geräte & Dienste → KVV Abfahrten*.

## Datenquellen

| Quelle | Status |
|---|---|
| `efa` (Standard) | Inoffizielle EFA-Schnittstelle `projekte.kvv-efa.de`, ohne Anmeldung, Echtzeit. Undokumentiert, kann sich ändern. |
| `trias` | Offizielle [KVV-Open-Data-Schnittstelle](https://www.kvv.de/fahrplan/fahrplaene/open-data.html) (VDV 431-2). Zugang per Nutzungsvereinbarung bei fahrplan@kvv.karlsruhe.de. |

Für TRIAS in den Einstellungen Quelle `trias`, die vom KVV mitgeteilte URL und
die Requestor-Referenz eintragen. Die Haltestellensuche läuft immer über EFA.
**Der TRIAS-Client ist nur gegen eine selbst geschriebene Beispielantwort
getestet**, nicht gegen den echten Server. Beim ersten Test mit echten
Zugangsdaten sind kleine Anpassungen (Authentifizierung, Namespaces,
Haltestellen-IDs) wahrscheinlich.

## Entwicklung

```
python -m venv venv && venv/bin/pip install aiohttp pytest pytest-asyncio
venv/bin/pytest tests
```
