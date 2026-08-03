<!-- Created by engelsofta in 2026 for the modified Engelsoft BACstac distribution. -->

# Engelsoft BACstac 1.2.0

Dieses Release schützt insbesondere BACnet-Geräte mit einer kleinen oder
empfindlichen COV-Implementierung.

## Sicherheits- und Stabilitätskorrekturen

- Neue Installationen verwenden standardmäßig `managed_polling`.
- Die bisherige Standard-COV-Liste `all` ist nun leer.
- Pro Gerät gelten standardmäßig maximal 20 gleichzeitige COV-Abonnements;
  weitere Objekte werden automatisch gepollt.
- COV-Anmeldungen werden mit einstellbarem Abstand aufgebaut.
- Fehlerhafte oder bestätigte, aber stumme COV-Abonnements wechseln automatisch
  auf Polling. Stumme Abonnements werden beendet, damit sie keinen Platz im Gerät
  belegen.
- Harmlose doppelte Anforderungen erscheinen nur noch im Debug-Protokoll.
- Die Abonnementseite zeigt je Ziel COV-Bestätigung, letzte COV-Nachricht,
  letzten Poll und Wertealter.

## Hinweis für bestehende Installationen

Home Assistant übernimmt geänderte Standardoptionen nicht automatisch in eine
bestehende Konfiguration. Bereits installierte Systeme sollten den Modus manuell
auf `managed_polling` stellen oder `managed_cov` nur mit einem zum BACnet-Gerät
passenden `CoV_limit` verwenden. Das Limit von 20 greift im Programm auch dann,
wenn es in einer älteren Konfiguration noch fehlt.
