# KVV Abfahrten

Zeigt Live-Abfahrten inkl. Verspätung (Soll-/Ist-Zeit, Ausfälle) für jede
Haltestelle im KVV-Netz. Datenquelle ist die EFA-Schnittstelle des KVV
(`projekte.kvv-efa.de`). Sie ist **inoffiziell und undokumentiert** und kann
sich jederzeit ändern.

## Optionen

| Option | Bedeutung |
|---|---|
| `default_stop` | Haltestellen-ID, die ohne `?stop=` angezeigt wird (z. B. `de:08212:3`) |
| `limit` | Anzahl angezeigter Abfahrten (1–40) |
| `cache_seconds` | So lange werden KVV-Antworten zwischengespeichert (schont den Server) |
| `walk_minutes` | Abfahrten, die in weniger Minuten fahren, werden ausgeblendet (Fußweg) |

## Haltestelle finden

Im Addon auf das Zahnrad klicken und nach dem Namen suchen, oder per API:
`http://HOMEASSISTANT:8099/api/stops?q=Marktplatz`. Die zurückgegebene `id`
(z. B. `7001003`) wird als `stop` verwendet.

## Einbindung ins Dashboard

**Webseiten-Karte** (YAML), direkt über den Port:

```yaml
type: iframe
url: http://HOMEASSISTANT:8099/?stop=de:08212:3&limit=8&compact=1
aspect_ratio: 100%
```

URL-Parameter: `stop`, `limit`, `lines` (kommagetrennt, z. B. `S1,S5,3`),
`theme` (`light`/`dark`, sonst automatisch), `compact` (ohne Kopfzeile),
`nosearch` (Zahnrad ausblenden), `refresh` (Sekunden, min. 15).

Läuft Home Assistant über HTTPS, blockiert der Browser eine `http://`-iframe
(Mixed Content). Dann Home Assistant lokal per HTTP aufrufen oder das Addon
hinter einen HTTPS-Reverse-Proxy stellen.

Zusätzlich erscheint das Addon über Ingress als Eintrag **KVV** in der Seitenleiste.

## JSON-API / Sensoren

`GET /api/departures?stop=ID&limit=N&lines=S1,S5` liefert u. a. `line`,
`direction`, `planned`, `actual`, `delay` (Minuten), `cancelled`. Beispiel für
die Verspätung der nächsten Abfahrt als Sensor:

```yaml
rest:
  - resource: http://localhost:8099/api/departures?stop=de:08212:3&limit=1
    scan_interval: 60
    sensor:
      - name: "KVV nächste Abfahrt Verspätung"
        value_template: "{{ value_json.departures[0].delay }}"
        unit_of_measurement: min
```
