<!-- Modified by engelsofta in 2026 for Engelsoft BACstac; derived from the Bepacom BACnet/IP add-on. -->

# Engelsoft BACstac für Home Assistant

**Deutsch** | [English](README.md)

[![Release](https://img.shields.io/github/v/release/engelsofta/engelsoft-bacstac-ha-addon?display_name=tag&cacheSeconds=300)](https://github.com/engelsofta/engelsoft-bacstac-ha-addon/releases/latest)
[![Build](https://github.com/engelsofta/engelsoft-bacstac-ha-addon/actions/workflows/build.yaml/badge.svg)](https://github.com/engelsofta/engelsoft-bacstac-ha-addon/actions/workflows/build.yaml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

Engelsoft BACstac verbindet ein BACnet/IP-Netzwerk mit Home Assistant. Das Add-on
übernimmt die BACnet-Kommunikation und stellt erkannte Geräte, Objekte und
Wertänderungen über eine lokale Schnittstelle für **Engelsoft Beacon BACnet/IP**
bereit.

## Vorteile

- **Automatische BACnet-Erkennung:** Findet erreichbare BACnet/IP-Geräte und liest
  deren Objektbestand ein.
- **Sichere Wertaktualisierung:** Startet standardmäßig mit verwaltetem Polling.
  Optionales COV wird pro Gerät begrenzt, gedrosselt aufgebaut und fällt bei
  ausbleibenden Meldungen automatisch auf Polling zurück.
- **Transparenter Zielstatus:** Zeigt je Objekt die bestätigte COV-Anmeldung,
  letzte COV-Nachricht, letzte Abfrage und das Alter des aktuellen Wertes.
- **Integrationsgesteuerter Hybridmodus:** Übernimmt COV, Polling oder deaktiviert
  pro Ziel aus Engelsoft Beacon BACnet/IP, ohne COV-Limits, Drosselung und
  automatische Fallbacks aus der Hand zu geben.
- **Robuster Neustart:** Ein versionierter, geprüfter Inventar-Cache stellt den
  zuletzt vollständig erkannten Objektbestand nach einem Neustart frühzeitig bereit.
- **Klare Aufgabentrennung:** BACstac kommuniziert mit BACnet; Engelsoft Beacon
  BACnet/IP kümmert sich in Home Assistant um Geräte und Entitäten.
- **Übersichtliche Weboberfläche:** Geräte, Objekte, Abonnements und Diagnosewerte
  lassen sich direkt über Home Assistant Ingress kontrollieren. Dark und Light
  Mode folgen dem Home-Assistant-Theme; Deutsch und Englisch folgen der gewählten
  Oberflächensprache.
- **BACnet-Schreibzugriffe:** Unterstützt Schreibanforderungen mit konfigurierbarer
  BACnet-Priorität.
- **Flexible Netzwerkanbindung:** Unterstützt den normalen BACnet/IP-Betrieb sowie
  Foreign-Device-Anmeldungen an einem BBMD.
- **Mehrsprachige Konfiguration:** Deutsche, englische und niederländische Texte
  sind enthalten.
- **Aktuelle Home-Assistant-Plattformen:** Vorgefertigte Images für `amd64` und
  `aarch64`, einschließlich aktueller Raspberry-Pi-Systeme mit 64-Bit-Home-Assistant.

## Zusammenspiel mit Engelsoft Beacon BACnet/IP

```text
BACnet/IP-Geräte
       ↓
Engelsoft BACstac
  Erkennung · Lesen/Schreiben · COV/Polling · Cache · Diagnose
       ↓
Engelsoft Beacon BACnet/IP
  Geräte und Entitäten in Home Assistant
```

Das Add-on erzeugt bewusst keine Home-Assistant-Entitäten. Diese Aufgabe übernimmt
die Integration **Engelsoft Beacon BACnet/IP**. Dadurch bleiben BACnet-Kommunikation
und Home-Assistant-Darstellung sauber voneinander getrennt.

## Installation

1. Öffne in Home Assistant **Einstellungen → Apps → App-Store**.
2. Öffne das Menü des App-Stores und wähle **Repositories**.
3. Füge dieses benutzerdefinierte Repository hinzu:

   `https://github.com/engelsofta/engelsoft-bacstac-ha-addon`

4. Installiere **Engelsoft BACstac**.
5. Konfiguriere die BACnet/IP-Verbindung und starte das Add-on.
6. Richte anschließend [**Engelsoft Beacon BACnet/IP**](https://github.com/engelsofta/ha-bepacom-bacnet) in Home Assistant ein.

Ausführliche Hinweise zu den Optionen stehen in der
[Add-on-Dokumentation](engelsoft_bacstac/DOCS.md).

## Unterstützte Architekturen

| Architektur | Typische Systeme |
| --- | --- |
| `amd64` | Home Assistant OS auf Intel- und AMD-Systemen |
| `aarch64` | 64-Bit-ARM-Systeme, darunter aktuelle Raspberry Pis |

32-Bit-ARM-Installationen werden von der eingesetzten offiziellen
Home-Assistant-Buildkette nicht mehr als Zielarchitektur veröffentlicht.

## Releases und Hilfe

Versionen und Änderungen findest du unter
[Releases](https://github.com/engelsofta/engelsoft-bacstac-ha-addon/releases) und
im [Changelog](engelsoft_bacstac/CHANGELOG.md). Die Container-Images werden für
alle unterstützten Architekturen gebaut und über GitHub Container Registry
bereitgestellt.

Prüfe vor einer Fehlermeldung bitte das Add-on-Protokoll und die Diagnoseansicht.
Fehler und nachvollziehbare Verbesserungsvorschläge kannst du über
[GitHub Issues](https://github.com/engelsofta/engelsoft-bacstac-ha-addon/issues)
melden.

## Lizenz und Herkunft

Engelsoft BACstac ist eine wesentlich veränderte Weiterentwicklung des
[Bepacom BACnet/IP Add-ons](https://github.com/Bepacom-Raalte/bepacom-HA-Addons).
Das Projekt wird unter der Apache License 2.0 verteilt. Die originale
[LICENSE](LICENSE), die Herkunftshinweise und die Kennzeichnung veränderter
Dateien bleiben erhalten. Weitere Angaben stehen in [NOTICE](NOTICE).
