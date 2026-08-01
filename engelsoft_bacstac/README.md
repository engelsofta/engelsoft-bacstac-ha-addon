<!-- Modified by engelsofta in 2026 for Engelsoft BACstac; derived from the Bepacom BACnet/IP add-on. -->

# Engelsoft BACstac

Engelsoft BACstac stellt die BACnet/IP-Verbindung für **Engelsoft Beacon
BACnet/IP** bereit. Das Add-on erkennt BACnet-Geräte, liest deren Objekte und
Werte, verwaltet COV-Abonnements beziehungsweise Polling und stellt die Daten der
Home-Assistant-Integration zur Verfügung.

## Das bringt das Add-on mit

- automatische Erkennung von BACnet/IP-Geräten und Objekten
- verwaltete COV-Abonnements mit kontrolliertem Polling als Alternative
- geprüfter Inventar-Cache für einen robusten Neustart
- Lesen und Schreiben von BACnet-Werten einschließlich Schreibpriorität
- Betrieb als normales BACnet/IP-Gerät oder als Foreign Device an einem BBMD
- Ingress-Weboberfläche für Geräte, Objekte, Abonnements und Diagnose
- deutsche, englische und niederländische Konfigurationstexte

## Wichtig: Integration und Add-on gehören zusammen

BACstac übernimmt die Kommunikation mit dem BACnet-Netzwerk. Die Integration
**Engelsoft Beacon BACnet/IP** erzeugt daraus die Geräte und Entitäten in Home
Assistant. Das Add-on selbst exportiert bewusst keine Home-Assistant-Entitäten.

Nach der Installation des Add-ons muss daher zusätzlich Engelsoft Beacon
BACnet/IP in Home Assistant eingerichtet werden.

Ausführliche Konfigurationshinweise findest du in der Registerkarte
**Dokumentation** beziehungsweise in [DOCS.md](DOCS.md).

## Unterstützung

Prüfe bei Problemen zuerst das Add-on-Protokoll und die Diagnoseansicht. Fehler
können im [GitHub-Repository](https://github.com/engelsofta/engelsoft-bacstac-ha-addon/issues)
gemeldet werden.

![Supports aarch64 Architecture][aarch64-shield]
![Supports amd64 Architecture][amd64-shield]

## Lizenz und Herkunft

Engelsoft BACstac ist eine wesentlich veränderte Weiterentwicklung des
[Bepacom BACnet/IP Add-ons](https://github.com/Bepacom-Raalte/bepacom-HA-Addons)
und wird unter der Apache License 2.0 verteilt. Die ursprüngliche Lizenz und die
Herkunftshinweise befinden sich im Wurzelverzeichnis des Repositories in
[`LICENSE`](../LICENSE) und [`NOTICE`](../NOTICE).

[aarch64-shield]: https://img.shields.io/badge/aarch64-yes-green.svg
[amd64-shield]: https://img.shields.io/badge/amd64-yes-green.svg
