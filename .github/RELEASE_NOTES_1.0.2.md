<!-- Created by engelsofta in 2026 for Engelsoft BACstac. -->

# Engelsoft BACstac 1.0.2

Dieses Wartungsupdate stellt die Live-Kommunikation zwischen BACstac, WebUI und
Engelsoft Beacon BACnet/IP wieder her.

## Behoben

- Die benötigte WebSocket-Laufzeitbibliothek ist wieder im Container enthalten.
- WebSocket-Upgrades auf `/ws` werden dadurch von Uvicorn korrekt angenommen.
- Die nginx-Verbindungsanzahl wurde an das Datei-Limit des Containers angepasst,
  sodass die entsprechende Startwarnung nicht mehr erscheint.

Betroffen waren insbesondere die Meldungen `Unsupported upgrade request` und
`No supported WebSocket library detected`.

## Installation

Im Home-Assistant-App-Store nach Updates suchen und **Engelsoft BACstac 1.0.2**
installieren.
