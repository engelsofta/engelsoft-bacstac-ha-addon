<!-- Created by engelsofta in 2026 for the modified Engelsoft BACstac distribution. -->

# Engelsoft BACstac 1.2.10

Der COV-Zähler behält während der Initialisierung jetzt seine feste Sollmenge.
Ein von der Integration als COV angeforderter Punkt bleibt auch beim Aufbau der
Subscription, beim Kontroll-Poll und bei einem möglichen Polling-Fallback als
COV-Ziel erfasst.

Damit zählt die linke Seite von null bis zur Anzahl der bestätigten
Anmeldungen hoch, während die rechte Seite stabil bleibt – beispielsweise von
`0 von 346` bis `346 von 346`.

Außerdem verarbeitet das Add-on die BACnet-Fähigkeitsinformationen jetzt sowohl
direkt vom Gerät als auch aus dem lokalen Inventar-Cache korrekt. Der gemeldete
Polling-Fehler `TypeError: list indices must be integers or slices, not str`
tritt damit bei wiederhergestellten Geräten nicht mehr auf.
