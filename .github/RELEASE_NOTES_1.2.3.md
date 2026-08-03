<!-- Created by engelsofta in 2026 for the modified Engelsoft BACstac distribution. -->

# Engelsoft BACstac 1.2.3

Dieses kleine UI-Release korrigiert die überlappende Leiste zur
Aktualisierungssteuerung.

- Auf breiten Ansichten sitzt die Modusübersicht sauber neben der Navigation.
- Auf schmaleren Ansichten erhält sie eine eigene Zeile mit automatischer Höhe.
- Zielstatus und Aktionsbereich werden nicht mehr von Elementen im Hintergrund
  überlagert.
- Eine neue Stylesheet-Version umgeht erneut ältere Ingress-Caches.
- Zielstatus und aktive COV-Tasks wurden zu einer einzigen Tabelle zusammengeführt.
- Aktives COV sowie Confirmed oder Unconfirmed sind direkt in der COV-Spalte sichtbar.
- Alle Spalten lassen sich per Klick sortieren; Zeitspalten werden numerisch sortiert.
- Die Tabelle aktualisiert ihren Status automatisch, ohne Filter, Sortierung oder markierte COV-Tasks zurückzusetzen.
- Wiederholte, unveränderte Ziellisten der Integration starten den gedrosselten COV-Aufbau nicht mehr neu; dadurch werden auch die hinteren Datenpunkte zuverlässig abgearbeitet.
