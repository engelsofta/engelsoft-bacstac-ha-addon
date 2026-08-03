<!-- Created by engelsofta in 2026 for the modified Engelsoft BACstac distribution. -->

# Engelsoft BACstac 1.2.1

Dieses Wartungsrelease behebt Verbindungsabbrüche, die auftreten konnten, wenn
Engelsoft Beacon BACnet/IP und die Add-on-Weboberfläche gleichzeitig per
WebSocket verbunden waren.

## Korrekturen

- Ein zentraler Broadcaster versorgt jetzt alle WebSocket-Clients genau einmal.
- COV-Polling-Fallbacks werden pro BACnet-Gerät in einem Worker gebündelt, statt
  für jeden Datenpunkt eine eigene endlose Aufgabe anzulegen.
- Alte Subscribe- und Unsubscribe-Aufrufe der Integration erhalten sofort eine
  eindeutige Bestätigung und erscheinen im integrationsgesteuerten Zielstatus.
- Wiederholte COV-Limit-Meldungen erscheinen nach der ersten Gerätewarnung nur
  noch im Debug-Protokoll.
