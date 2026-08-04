<!-- Created by engelsofta in 2026 for the modified Engelsoft BACstac distribution. -->

# Engelsoft BACstac 1.2.9

Der COV-Fortschritt ist jetzt eindeutig und stabil:

- rechts stehen alle von der Integration erwarteten COV-Ziele;
- links stehen alle Ziele, deren COV-Anmeldung seit dem Add-on-Start mindestens
  einmal bestätigt wurde;
- Erneuerungen, temporärer Neuaufbau oder Fallback lassen den bestätigten
  Fortschritt nicht mehr rückwärts zählen.

Der Abstand zwischen COV-Anmeldungen wird nun in Millisekunden eingestellt.
`1000 ms` entsprechen dem bisherigen Standard von einer Sekunde; beispielsweise
ermöglichen `250 ms` vier Anmeldeversuche pro Sekunde. Bestehende Sekundenwerte
bleiben als Fallback kompatibel.

Der Polling-Worker ist jetzt gegen einzelne fehlerhafte BACnet-Punkte und
Zeitüberschreitungen abgesichert. Er arbeitet nach einem Fehler weiter, erholt
sich automatisch von unerwarteten Zyklusfehlern und zeigt betroffene Ziele als
„Polling gestört“ samt letzter Ursache. Zusätzliche Diagnosewerte dokumentieren
Zyklusdauer, Lesefehler und Wiederherstellungen.
