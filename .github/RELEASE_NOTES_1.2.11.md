<!-- Created by engelsofta in 2026 for the modified Engelsoft BACstac distribution. -->

# Engelsoft BACstac 1.2.11

Aus dem Inventar-Cache bekannte Polling-Punkte können bereits von der Integration
angefordert werden, bevor das BACnet-Gerät nach einem Neustart seine aktuelle
Netzwerkadresse gemeldet hat. Diese Startreihenfolge führte bisher zu einer
leeren `AssertionError`-Meldung.

BACstac wartet nun mit dem Polling, bis eine live bestätigte Geräteadresse
vorliegt. Währenddessen zeigt die Übersicht **Wartet auf Gerät** an und sendet
höchstens alle 30 Sekunden eine gezielte Who-Is-Anfrage. Nach dem ersten I-Am
beginnt das Polling automatisch.
